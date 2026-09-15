"""OpenAlex REST API source adapter."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

import httpx

from backend.config import DISCOVERY_QUERIES
from backend.ingestion.base import SourceFetchError
from backend.ingestion.http import get_with_retry
from backend.ingestion.schema import PaperRecord


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    """Rebuild an OpenAlex abstract from its token-position inverted index."""

    if not inverted_index:
        return None
    positioned = [
        (position, token)
        for token, positions in inverted_index.items()
        for position in positions
        if isinstance(position, int) and position >= 0
    ]
    if not positioned:
        return None
    return " ".join(token for _, token in sorted(positioned))


class OpenAlexSource:
    name = "openalex"
    base_url = "https://api.openalex.org"

    def __init__(
        self,
        *,
        mailto: str | None = None,
        timeout_seconds: float = 30.0,
        client: Any | None = None,
        queries: tuple[str, ...] = DISCOVERY_QUERIES,
    ) -> None:
        self.mailto = mailto
        self.timeout_seconds = timeout_seconds
        self._client = client
        self.queries = queries

    async def fetch(
        self,
        start_date: date,
        end_date: date,
        *,
        limit: int,
    ) -> list[PaperRecord]:
        if limit < 1 or not self.queries:
            return []

        if self._client is not None:
            return await self._fetch_with_client(self._client, start_date, end_date, limit)

        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers={"User-Agent": "ArxivSentinel/0.1"},
            timeout=self.timeout_seconds,
        ) as client:
            return await self._fetch_with_client(client, start_date, end_date, limit)

    async def _fetch_with_client(
        self,
        client: Any,
        start_date: date,
        end_date: date,
        limit: int,
    ) -> list[PaperRecord]:
        records: dict[str, PaperRecord] = {}
        per_query = min(200, max(1, math.ceil(limit / len(self.queries))))
        inclusive_end = date.fromordinal(end_date.toordinal() - 1)

        try:
            for query in self.queries:
                params: dict[str, str | int] = {
                    "search": query,
                    "filter": (
                        f"from_publication_date:{start_date.isoformat()},"
                        f"to_publication_date:{inclusive_end.isoformat()}"
                    ),
                    "per-page": per_query,
                    "sort": "publication_date:desc",
                }
                if self.mailto:
                    params["mailto"] = self.mailto
                response = await get_with_retry(client, "/works", params=params)
                response.raise_for_status()
                for item in response.json().get("results", []):
                    record = self._to_record(item)
                    if record is not None:
                        records[record.source_ids["openalex"]] = record
                if len(records) >= limit:
                    break
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise SourceFetchError(f"OpenAlex request failed: {exc}") from exc

        return list(records.values())[:limit]

    @staticmethod
    def _to_record(item: dict[str, Any]) -> PaperRecord | None:
        abstract = reconstruct_abstract(item.get("abstract_inverted_index"))
        published = item.get("publication_date")
        openalex_url = item.get("id")
        if not abstract or not published or not openalex_url:
            return None

        openalex_id = str(openalex_url).rstrip("/").rsplit("/", maxsplit=1)[-1]
        source_ids = {"openalex": openalex_id}
        ids = item.get("ids") or {}
        if ids.get("arxiv"):
            source_ids["arxiv"] = str(ids["arxiv"]).rstrip("/").rsplit("/", 1)[-1]
        if ids.get("doi"):
            source_ids["doi"] = str(ids["doi"]).removeprefix("https://doi.org/").lower()

        location = item.get("primary_location") or {}
        authors = [
            authorship["author"]["display_name"]
            for authorship in item.get("authorships", [])
            if (authorship.get("author") or {}).get("display_name")
        ]
        return PaperRecord(
            title=item["title"],
            abstract=abstract,
            authors=authors,
            published_date=date.fromisoformat(published),
            source_ids=source_ids,
            source_urls={"openalex": location.get("landing_page_url") or str(openalex_url)},
            citation_count=item.get("cited_by_count"),
        )
