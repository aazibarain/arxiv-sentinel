import asyncio
from datetime import date

from backend.filtering.relevance import RelevanceFilter
from backend.ingestion.schema import PaperRecord
from backend.memory.novelty import NoveltyDetector
from backend.memory.vector_store import ChromaVectorStore
from backend.pipeline import run_phase_one, run_pipeline
from tests.test_relevance import MappingEmbedder


class FakeSource:
    def __init__(self, name: str, papers: list[PaperRecord] | None = None, error: str = "") -> None:
        self.name = name
        self.papers = papers or []
        self.error = error

    async def fetch(self, start_date: date, end_date: date, *, limit: int) -> list[PaperRecord]:
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


def test_full_pipeline_remembers_paper_and_detects_rerun(tmp_path: object) -> None:
    abstract = "A prompt injection attack"
    vectors = {"prototype": [1.0, 0.0], abstract: [1.0, 0.0]}
    relevance = RelevanceFilter(MappingEmbedder(vectors), threshold=0.5, references=("prototype",))
    detector = NoveltyDetector(ChromaVectorStore(tmp_path))

    def new_record() -> PaperRecord:
        return PaperRecord(
            title="Agent Attack",
            abstract=abstract,
            authors=["Researcher"],
            published_date=date(2026, 9, 15),
            source_ids={"arxiv": "2609.10000"},
            source_urls={"arxiv": "https://arxiv.org/abs/2609.10000"},
        )

    first = asyncio.run(
        run_pipeline(
            date(2026, 9, 15),
            sources=[FakeSource("arxiv", [new_record()])],
            relevance_filter=relevance,
            novelty_detector=detector,
        )
    )
    second = asyncio.run(
        run_pipeline(
            date(2026, 9, 15),
            sources=[FakeSource("arxiv", [new_record()])],
            relevance_filter=relevance,
            novelty_detector=detector,
        )
    )

    assert first.relevant[0].novelty_verdict == "novel"
    assert first.memory_count_before == 0
    assert first.memory_count_after == 1
    assert second.relevant[0].novelty_verdict == "duplicate"
    assert second.memory_count_before == 1
    assert second.memory_count_after == 1
