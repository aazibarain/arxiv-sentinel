"""Read-only research tools available to the summarization agent."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field

from backend.filtering.embed import TextEmbedder
from backend.ingestion.http import get_with_retry
from backend.ingestion.schema import PaperRecord, SimilarPaper
from backend.memory.vector_store import PaperMemory


class CitationPaper(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    url: str | None = None
    citation_count: int | None = None


class OpenAlexMetadata(BaseModel):
    openalex_id: str
    title: str
    publication_date: str | None = None
    citation_count: int | None = None
    source_url: str | None = None


class ResearchContext(BaseModel):
    memory_matches: list[SimilarPaper] = Field(default_factory=list)
    citing_papers: list[CitationPaper] = Field(default_factory=list)
    openalex: OpenAlexMetadata | None = None
    tool_errors: dict[str, str] = Field(default_factory=dict)


class ResearchTools:
    """Deterministic tools that collect context before Gemini reasons."""

    semantic_scholar_url = "https://api.semanticscholar.org/graph/v1"
    openalex_url = "https://api.openalex.org"

    def __init__(
        self,
        *,
        memory: PaperMemory,
        embedder: TextEmbedder,
        timeout_seconds: float = 30.0,
        openalex_mailto: str | None = None,
        semantic_scholar_client: Any | None = None,
        openalex_client: Any | None = None,
    ) -> None:
        self.memory = memory
        self.embedder = embedder
        self.timeout_seconds = timeout_seconds
        self.openalex_mailto = openalex_mailto
        self._semantic_scholar_client = semantic_scholar_client
        self._openalex_client = openalex_client

    async def query_memory(self, query: str, *, k: int = 5) -> list[SimilarPaper]:
        vectors = await asyncio.to_thread(self.embedder.embed, [query])
        return await asyncio.to_thread(
            self.memory.query_similar,
            vectors[0].tolist(),
            k=k,
        )

    async def fetch_semantic_scholar_citations(
        self,
        paper_id: str,
        *,
        limit: int = 10,
    ) -> list[CitationPaper]:
        """Fetch papers that cite the supplied Semantic Scholar-compatible ID."""

        if self._semantic_scholar_client is not None:
            return await self._fetch_s2_with_client(self._semantic_scholar_client, paper_id, limit)
        async with httpx.AsyncClient(
            base_url=self.semantic_scholar_url,
            headers={"User-Agent": "ArxivSentinel/0.1"},
            timeout=self.timeout_seconds,
        ) as client:
            return await self._fetch_s2_with_client(client, paper_id, limit)

    async def _fetch_s2_with_client(
        self,
        client: Any,
        paper_id: str,
        limit: int,
    ) -> list[CitationPaper]:
        response = await get_with_retry(
            client,
            f"/paper/{quote(paper_id, safe='')}/citations",
            params={"fields": "title,url,authors,year,citationCount", "limit": limit},
        )
        response.raise_for_status()
        citations = []
        for item in response.json().get("data", []):
            citing = item.get("citingPaper") or {}
            if not citing.get("title"):
                continue
            citations.append(
                CitationPaper(
                    title=citing["title"],
                    authors=[
                        author["name"] for author in citing.get("authors", []) if author.get("name")
                    ],
                    year=citing.get("year"),
                    url=citing.get("url"),
                    citation_count=citing.get("citationCount"),
                )
            )
        return citations

    async def fetch_openalex_metadata(self, paper_id: str) -> OpenAlexMetadata:
        if self._openalex_client is not None:
            return await self._fetch_openalex_with_client(self._openalex_client, paper_id)
        async with httpx.AsyncClient(
            base_url=self.openalex_url,
            headers={"User-Agent": "ArxivSentinel/0.1"},
            timeout=self.timeout_seconds,
        ) as client:
            return await self._fetch_openalex_with_client(client, paper_id)

    async def _fetch_openalex_with_client(
        self,
        client: Any,
        paper_id: str,
    ) -> OpenAlexMetadata:
        params = {"mailto": self.openalex_mailto} if self.openalex_mailto else {}
        response = await get_with_retry(
            client,
            f"/works/{quote(paper_id, safe='')}",
            params=params,
        )
        response.raise_for_status()
        item = response.json()
        openalex_url = str(item["id"])
        location = item.get("primary_location") or {}
        return OpenAlexMetadata(
            openalex_id=openalex_url.rstrip("/").rsplit("/", 1)[-1],
            title=item.get("display_name") or item["title"],
            publication_date=item.get("publication_date"),
            citation_count=item.get("cited_by_count"),
            source_url=location.get("landing_page_url") or openalex_url,
        )

    async def build_context(self, paper: PaperRecord) -> ResearchContext:
        """Gather all available tool context without making one failure fatal."""

        context = ResearchContext(memory_matches=paper.novelty_matches)
        if not context.memory_matches:
            try:
                context.memory_matches = await self.query_memory(paper.abstract, k=5)
            except Exception as exc:
                context.tool_errors["query_memory"] = str(exc)

        tasks: dict[str, Any] = {}
        if citation_id := _semantic_scholar_identifier(paper):
            tasks["semantic_scholar_citations"] = self.fetch_semantic_scholar_citations(citation_id)
        if openalex_id := _openalex_identifier(paper):
            tasks["openalex_metadata"] = self.fetch_openalex_metadata(openalex_id)

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for name, result in zip(tasks, results, strict=True):
            if isinstance(result, BaseException):
                context.tool_errors[name] = str(result)
            elif name == "semantic_scholar_citations":
                context.citing_papers = result
            elif name == "openalex_metadata":
                context.openalex = result
        return context


def _semantic_scholar_identifier(paper: PaperRecord) -> str | None:
    if value := paper.source_ids.get("semantic_scholar"):
        return value
    if value := paper.source_ids.get("arxiv"):
        return f"ARXIV:{value}"
    if value := paper.source_ids.get("doi"):
        return f"DOI:{value}"
    return None


def _openalex_identifier(paper: PaperRecord) -> str | None:
    if value := paper.source_ids.get("openalex"):
        return value
    if value := paper.source_ids.get("doi"):
        return f"https://doi.org/{value}"
    return None
