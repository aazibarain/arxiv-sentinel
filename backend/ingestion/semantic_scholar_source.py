"""Semantic Scholar Academic Graph source adapter."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

import httpx

from backend.config import DISCOVERY_QUERIES
from backend.ingestion.base import SourceFetchError
from backend.ingestion.http import get_with_retry
from backend.ingestion.schema import PaperRecord


class SemanticScholarSource:
    name = "semantic_scholar"
    base_url = "https://api.semanticscholar.org/graph/v1"
    fields = "paperId,externalIds,url,title,abstract,authors,publicationDate,citationCount"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
        client: Any | None = None,
        queries: tuple[str, ...] = DISCOVERY_QUERIES,
    ) -> None:
        self.api_key = api_key
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

        headers = {"User-Agent": "ArxivSentinel/0.1"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
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
        per_query = min(100, max(1, math.ceil(limit / len(self.queries))))
        inclusive_end = date.fromordinal(end_date.toordinal() - 1)

        try:
            for query in self.queries:
                response = await get_with_retry(
                    client,
                    "/paper/search",
                    params={
                        "query": query,
                        "publicationDateOrYear": (
                            f"{start_date.isoformat()}:{inclusive_end.isoformat()}"
                        ),
                        "fields": self.fields,
                        "limit": per_query,
                    },
                )
                response.raise_for_status()
                for item in response.json().get("data", []):
                    record = self._to_record(item)
                    if record is not None:
                        records[record.source_ids["semantic_scholar"]] = record
                if len(records) >= limit:
                    break
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise SourceFetchError(f"Semantic Scholar request failed: {exc}") from exc

        return list(records.values())[:limit]

    @staticmethod
    def _to_record(item: dict[str, Any]) -> PaperRecord | None:
        abstract = item.get("abstract")
        published = item.get("publicationDate")
        paper_id = item.get("paperId")
        if not abstract or not published or not paper_id:
            return None

        external_ids = item.get("externalIds") or {}
        source_ids = {"semantic_scholar": str(paper_id)}
        if external_ids.get("ArXiv"):
            source_ids["arxiv"] = str(external_ids["ArXiv"])
        if external_ids.get("DOI"):
            source_ids["doi"] = str(external_ids["DOI"]).lower()

        authors = [author["name"] for author in item.get("authors", []) if author.get("name")]
        return PaperRecord(
            title=item["title"],
            abstract=abstract,
            authors=authors,
            published_date=date.fromisoformat(published),
            source_ids=source_ids,
            source_urls={
                "semantic_scholar": item.get("url")
                or f"https://www.semanticscholar.org/paper/{paper_id}"
            },
            citation_count=item.get("citationCount"),
        )
