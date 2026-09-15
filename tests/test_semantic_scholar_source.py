import asyncio
from datetime import date
from typing import Any

from backend.ingestion.semantic_scholar_source import SemanticScholarSource


class StubResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class StubClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def get(self, path: str, *, params: dict[str, Any]) -> StubResponse:
        self.calls.append((path, params))
        return StubResponse(self.payload)


def test_semantic_scholar_fetch_normalizes_and_filters_missing_abstracts() -> None:
    payload = {
        "data": [
            {
                "paperId": "s2-paper",
                "externalIds": {"ArXiv": "2609.12345", "DOI": "10.1/EXAMPLE"},
                "url": "https://www.semanticscholar.org/paper/s2-paper",
                "title": "Secure Agents",
                "abstract": "We study tool-call security.",
                "authors": [{"name": "Ada Lovelace"}],
                "publicationDate": "2026-09-15",
                "citationCount": 7,
            },
            {
                "paperId": "no-abstract",
                "title": "Unavailable",
                "abstract": None,
                "publicationDate": "2026-09-15",
            },
        ]
    }
    client = StubClient(payload)
    source = SemanticScholarSource(client=client, queries=("AI security",))

    papers = asyncio.run(source.fetch(date(2026, 9, 15), date(2026, 9, 16), limit=10))

    assert len(papers) == 1
    assert papers[0].source_ids == {
        "semantic_scholar": "s2-paper",
        "arxiv": "2609.12345",
        "doi": "10.1/example",
    }
    assert papers[0].citation_count == 7
    assert client.calls[0][0] == "/paper/search"
    assert client.calls[0][1]["publicationDateOrYear"] == "2026-09-15:2026-09-15"
