"""arXiv source adapter."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterable
from datetime import date
from typing import Any

import requests

from backend.ingestion.base import SourceFetchError
from backend.ingestion.schema import PaperRecord

ARXIV_CATEGORY_QUERY = " OR ".join(
    f"cat:{category}" for category in ("cs.CR", "cs.AI", "cs.LG", "stat.ML")
)


def _arxiv_id(entry_id: str) -> str:
    """Extract a stable arXiv identifier and discard the revision suffix."""

    raw_id = entry_id.rstrip("/").rsplit("/", maxsplit=1)[-1]
    return re.sub(r"v\d+$", "", raw_id)


class _TimeoutSession(requests.Session):
    """Supply the timeout omitted by arxiv.py's internal session."""

    def __init__(self, timeout_seconds: float) -> None:
        super().__init__()
        self.timeout_seconds = timeout_seconds

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout_seconds)
        return super().request(method, url, **kwargs)


class ArxivSource:
    name = "arxiv"

    def __init__(self, client: Any | None = None, *, timeout_seconds: float = 30.0) -> None:
        self._client = client
        self.timeout_seconds = timeout_seconds

    async def fetch(
        self,
        start_date: date,
        end_date: date,
        *,
        limit: int,
    ) -> list[PaperRecord]:
        if limit < 1:
            return []
        return await asyncio.to_thread(self._fetch_sync, start_date, end_date, limit)

    def _fetch_sync(self, start_date: date, end_date: date, limit: int) -> list[PaperRecord]:
        try:
            import arxiv
        except ImportError as exc:  # pragma: no cover - exercised in real setup
            raise SourceFetchError("The 'arxiv' package is not installed") from exc

        client = self._client or arxiv.Client(
            page_size=min(100, max(50, limit)),
            delay_seconds=3,
            num_retries=1,
        )
        if self._client is None:
            # arxiv.py does not expose an HTTP timeout. Its session is intentionally
            # replaceable and this prevents one provider from hanging a daily run.
            client._session = _TimeoutSession(self.timeout_seconds)
        # Fetch extra recent records because local date filtering may discard results
        # around weekends and arXiv announcement boundaries.
        search = arxiv.Search(
            query=ARXIV_CATEGORY_QUERY,
            max_results=min(max(limit * 5, 100), 1000),
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        try:
            entries: Iterable[Any] = client.results(search)
            records = []
            for entry in entries:
                published = entry.published.date()
                if start_date <= published < end_date:
                    records.append(self._to_record(entry))
                    if len(records) >= limit:
                        break
                elif published < start_date:
                    break
            return records
        except Exception as exc:
            raise SourceFetchError(f"arXiv request failed: {exc}") from exc

    @staticmethod
    def _to_record(entry: Any) -> PaperRecord:
        paper_id = _arxiv_id(entry.entry_id)
        return PaperRecord(
            title=entry.title,
            abstract=entry.summary,
            authors=[author.name for author in entry.authors],
            published_date=entry.published.date(),
            source_ids={"arxiv": paper_id},
            source_urls={"arxiv": f"https://arxiv.org/abs/{paper_id}"},
        )
