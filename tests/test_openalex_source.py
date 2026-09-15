import asyncio
from datetime import date
from typing import Any

from backend.ingestion.openalex_source import OpenAlexSource, reconstruct_abstract


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


def test_reconstruct_abstract_uses_token_positions() -> None:
    inverted = {"security": [3], "Agent": [0], "research": [2], "advances": [1]}
    assert reconstruct_abstract(inverted) == "Agent advances research security"


def test_openalex_fetch_normalizes_work() -> None:
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "ids": {
                    "doi": "https://doi.org/10.1/EXAMPLE",
                    "arxiv": "https://arxiv.org/abs/2609.12345",
                },
                "title": "Secure Agents",
                "abstract_inverted_index": {
                    "We": [0],
                    "study": [1],
                    "agent": [2],
                    "security.": [3],
                },
                "publication_date": "2026-09-15",
                "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
                "primary_location": {"landing_page_url": "https://example.test/paper"},
                "cited_by_count": 3,
            }
        ]
    }
    client = StubClient(payload)
    source = OpenAlexSource(client=client, mailto="owner@example.com", queries=("AI security",))

    papers = asyncio.run(source.fetch(date(2026, 9, 15), date(2026, 9, 16), limit=10))

    assert len(papers) == 1
    assert papers[0].abstract == "We study agent security."
    assert papers[0].source_ids == {
        "openalex": "W123",
        "arxiv": "2609.12345",
        "doi": "10.1/example",
    }
    assert client.calls[0][1]["mailto"] == "owner@example.com"
    assert client.calls[0][1]["filter"] == (
        "from_publication_date:2026-09-15,to_publication_date:2026-09-15"
    )
