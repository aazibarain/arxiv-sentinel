from datetime import date

import pytest

from backend.ingestion.schema import PaperRecord
from backend.memory.novelty import NoveltyDetector, NoveltyThresholds
from backend.memory.vector_store import ChromaVectorStore, memory_id_for


def paper(title: str, source_id: str, embedding: list[float]) -> PaperRecord:
    return PaperRecord(
        title=title,
        abstract=f"Abstract for {title}",
        authors=["Researcher"],
        published_date=date(2026, 9, 15),
        source_ids={"arxiv": source_id},
        source_urls={"arxiv": f"https://arxiv.org/abs/{source_id}"},
        embedding=embedding,
        relevance_score=0.9,
    )


def test_constructed_novelty_cases_and_persistence(tmp_path: object) -> None:
    memory = ChromaVectorStore(tmp_path)
    detector = NoveltyDetector(memory)

    known = detector.process([paper("Known attack", "1", [1.0, 0.0])])[0]
    incremental = detector.process([paper("Related defense", "2", [0.8, 0.6])])[0]
    duplicate = detector.process([paper("Known attack rephrased", "3", [1.0, 0.0])])[0]
    different = detector.process([paper("Different security topic", "4", [0.0, 1.0])])[0]

    assert known.novelty_verdict == "novel"
    assert known.novelty_score == 1.0
    assert incremental.novelty_verdict == "incremental"
    assert incremental.novelty_matches[0].title == "Known attack"
    assert incremental.novelty_matches[0].similarity == pytest.approx(0.8, abs=1e-5)
    assert duplicate.novelty_verdict == "duplicate"
    assert duplicate.novelty_matches[0].similarity == pytest.approx(1.0, abs=1e-5)
    assert different.novelty_verdict == "novel"

    reopened = ChromaVectorStore(tmp_path)
    assert reopened.count() == 4
    closest = reopened.query_similar([1.0, 0.0], k=2)[0]
    assert closest.similarity == pytest.approx(1.0, abs=1e-5)
    assert closest.source_urls["arxiv"].startswith("https://arxiv.org/abs/")


def test_memory_id_prefers_cross_source_identifier() -> None:
    record = paper("Paper", "2609.12345", [1.0, 0.0])
    record.source_ids["semantic_scholar"] = "S2"
    assert memory_id_for(record) == "arxiv:2609.12345"


@pytest.mark.parametrize(
    ("incremental", "duplicate"),
    [(0.9, 0.8), (-0.1, 0.9), (0.5, 1.1)],
)
def test_invalid_novelty_thresholds_are_rejected(incremental: float, duplicate: float) -> None:
    with pytest.raises(ValueError):
        NoveltyThresholds(incremental=incremental, duplicate=duplicate)
