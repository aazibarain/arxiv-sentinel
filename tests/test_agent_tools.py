import asyncio
from datetime import date
from typing import Any

import numpy as np

from backend.agent.tools import ResearchTools
from backend.ingestion.schema import PaperRecord, SimilarPaper


class StubResponse:
    status_code = 200
    headers: dict[str, str] = {}

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class StubClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.paths: list[str] = []

    async def get(self, path: str, *, params: dict[str, Any]) -> StubResponse:
        self.paths.append(path)
        return StubResponse(self.payload)


class UnusedEmbedder:
    def embed(self, texts: list[str]) -> np.ndarray[Any, Any]:
        raise AssertionError("existing novelty matches should be reused")


class UnusedMemory:
    def count(self) -> int:
        return 1

    def query_similar(self, embedding: list[float], *, k: int) -> list[SimilarPaper]:
        raise AssertionError("existing novelty matches should be reused")

    def upsert(self, papers: list[PaperRecord]) -> None:
        return None


def test_research_tools_build_context_from_keyless_sources() -> None:
    s2 = StubClient(
        {
            "data": [
                {
                    "citingPaper": {
                        "title": "Follow-up Work",
                        "authors": [{"name": "Ada"}],
                        "year": 2026,
                        "url": "https://example.test/follow-up",
                        "citationCount": 2,
                    }
                }
            ]
        }
    )
    openalex = StubClient(
        {
            "id": "https://openalex.org/W123",
            "display_name": "Secure Prompting",
            "publication_date": "2026-09-15",
            "cited_by_count": 4,
            "primary_location": {"landing_page_url": "https://example.test/paper"},
        }
    )
    tools = ResearchTools(
        memory=UnusedMemory(),
        embedder=UnusedEmbedder(),
        semantic_scholar_client=s2,
        openalex_client=openalex,
    )
    paper = PaperRecord(
        title="Secure Prompting",
        abstract="A sufficiently detailed security abstract.",
        authors=["Researcher"],
        published_date=date(2026, 9, 15),
        source_ids={"arxiv": "2609.12345", "openalex": "W123"},
        source_urls={"arxiv": "https://arxiv.org/abs/2609.12345"},
        novelty_matches=[
            SimilarPaper(
                memory_id="arxiv:old",
                title="Prior work",
                published_date=date(2026, 9, 1),
                similarity=0.8,
            )
        ],
    )

    context = asyncio.run(tools.build_context(paper))

    assert context.citing_papers[0].title == "Follow-up Work"
    assert context.openalex is not None and context.openalex.openalex_id == "W123"
    assert s2.paths == ["/paper/ARXIV%3A2609.12345/citations"]
    assert openalex.paths == ["/works/W123"]
    assert context.tool_errors == {}
