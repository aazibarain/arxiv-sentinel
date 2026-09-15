import asyncio
from datetime import date

from backend.filtering.relevance import RelevanceFilter
from backend.ingestion.schema import PaperRecord
from backend.pipeline import run_phase_one
from tests.test_relevance import MappingEmbedder


class FakeSource:
    def __init__(self, name: str, papers: list[PaperRecord] | None = None, error: str = "") -> None:
        self.name = name
        self.papers = papers or []
        self.error = error

    async def fetch(
        self, start_date: date, end_date: date, *, limit: int
    ) -> list[PaperRecord]:
        if self.error:
            raise RuntimeError(self.error)
        return self.papers[:limit]


def test_pipeline_isolates_source_failure() -> None:
    abstract = "Security research"
    record = PaperRecord(
        title="Paper",
        abstract=abstract,
        authors=["Researcher"],
        published_date=date(2026, 9, 15),
        source_ids={"arxiv": "1"},
        source_urls={"arxiv": "https://example.test"},
    )
    relevance = RelevanceFilter(
        MappingEmbedder({"prototype": [1.0, 0.0], abstract: [1.0, 0.0]}),
        threshold=0.5,
        references=("prototype",),
    )

    result = asyncio.run(
        run_phase_one(
            date(2026, 9, 15),
            sources=[FakeSource("working", [record]), FakeSource("broken", error="rate limited")],
            relevance_filter=relevance,
        )
    )

    assert result.relevant == [record]
    assert result.source_counts == {"working": 1, "broken": 0}
    assert result.source_errors == {"broken": "rate limited"}
