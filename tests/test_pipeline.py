import asyncio
from datetime import date

from backend.agent.summarizer import GroundedSummary
from backend.agent.tools import ResearchContext
from backend.config import Settings
from backend.filtering.relevance import RelevanceFilter
from backend.ingestion.schema import PaperRecord
from backend.memory.novelty import NoveltyDetector
from backend.memory.vector_store import ChromaVectorStore
from backend.pipeline import run_agent, run_phase_one, run_pipeline
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


def test_full_pipeline_reconciles_cross_source_duplicate_before_memory(
    tmp_path: object,
) -> None:
    first_abstract = "A prompt injection attack against an autonomous agent."
    second_abstract = (
        "A prompt injection attack against an autonomous agent with a detailed evaluation."
    )
    vectors = {
        "prototype": [1.0, 0.0],
        first_abstract: [1.0, 0.0],
        second_abstract: [1.0, 0.0],
    }
    relevance = RelevanceFilter(MappingEmbedder(vectors), threshold=0.5, references=("prototype",))
    detector = NoveltyDetector(ChromaVectorStore(tmp_path))
    arxiv = PaperRecord(
        title="Agent Attack",
        abstract=first_abstract,
        authors=["Researcher One"],
        published_date=date(2026, 9, 15),
        source_ids={"arxiv": "2609.30000"},
        source_urls={"arxiv": "https://arxiv.org/abs/2609.30000"},
    )
    semantic_scholar = PaperRecord(
        title="Agent Attack",
        abstract=second_abstract,
        authors=["Researcher One"],
        published_date=date(2026, 9, 15),
        source_ids={"arxiv": "2609.30000", "semantic_scholar": "S2-30000"},
        source_urls={"semantic_scholar": "https://example.test/S2-30000"},
    )

    result = asyncio.run(
        run_pipeline(
            date(2026, 9, 15),
            sources=[
                FakeSource("arxiv", [arxiv]),
                FakeSource("semantic_scholar", [semantic_scholar]),
            ],
            relevance_filter=relevance,
            novelty_detector=detector,
        )
    )

    assert result.relevant_count_before_reconciliation == 2
    assert result.reconciliation_merged_count == 1
    assert len(result.relevant) == 1
    assert result.memory_count_after == 1
    assert set(result.relevant[0].source_ids) == {"arxiv", "semantic_scholar"}


class FakeResearchTools:
    async def build_context(self, paper: PaperRecord) -> ResearchContext:
        return ResearchContext(memory_matches=paper.novelty_matches)


class FakeSummarizer:
    def __init__(self) -> None:
        self.calls = 0

    def summarize(self, paper: PaperRecord, context: ResearchContext) -> GroundedSummary:
        self.calls += 1
        output = GroundedSummary(
            summary="The paper studies a prompt injection attack against an autonomous agent.",
            why_it_matters="The prompt injection attack exposes a security weakness in the agent.",
            citations=[
                {
                    "claim": (
                        "The paper studies a prompt injection attack against an autonomous agent."
                    ),
                    "source_span": "The paper studies a prompt injection attack",
                },
                {
                    "claim": (
                        "The prompt injection attack exposes a security weakness in the agent."
                    ),
                    "source_span": "prompt injection attack against an autonomous agent",
                },
            ],
        )
        paper.summary = output.summary
        paper.why_it_matters = output.why_it_matters
        paper.summary_citations = output.citations
        return output


def test_phase_three_summarizes_novel_papers_and_skips_rerun_duplicates(
    tmp_path: object,
) -> None:
    abstract = (
        "The paper studies a prompt injection attack against an autonomous agent "
        "and exposes a security weakness."
    )
    vectors = {"prototype": [1.0, 0.0], abstract: [1.0, 0.0]}
    relevance = RelevanceFilter(MappingEmbedder(vectors), threshold=0.5, references=("prototype",))
    detector = NoveltyDetector(ChromaVectorStore(tmp_path))
    summarizer = FakeSummarizer()
    settings = Settings(_env_file=None)

    def new_record() -> PaperRecord:
        return PaperRecord(
            title="Agent Attack",
            abstract=abstract,
            authors=["Researcher"],
            published_date=date(2026, 9, 15),
            source_ids={"arxiv": "2609.20000"},
            source_urls={"arxiv": "https://arxiv.org/abs/2609.20000"},
        )

    first = asyncio.run(
        run_agent(
            date(2026, 9, 15),
            settings=settings,
            sources=[FakeSource("arxiv", [new_record()])],
            relevance_filter=relevance,
            novelty_detector=detector,
            research_tools=FakeResearchTools(),
            summarizer=summarizer,
        )
    )
    second = asyncio.run(
        run_agent(
            date(2026, 9, 15),
            settings=settings,
            sources=[FakeSource("arxiv", [new_record()])],
            relevance_filter=relevance,
            novelty_detector=detector,
            research_tools=FakeResearchTools(),
            summarizer=summarizer,
        )
    )

    assert first.summarized_count == 1
    assert first.relevant[0].summary is not None
    assert second.skipped_duplicate_count == 1
    assert second.summarized_count == 0
    assert summarizer.calls == 1
