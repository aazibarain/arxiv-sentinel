from datetime import date

from backend.db.models import DigestStore
from backend.ingestion.schema import PaperRecord


def make_paper(canonical_id: str, title: str = "Secure Agents") -> PaperRecord:
    return PaperRecord(
        canonical_id=canonical_id,
        title=title,
        abstract="The study evaluates prompt injection attacks against tool-using agents.",
        authors=["Ada Researcher"],
        published_date=date(2026, 9, 18),
        source_ids={"arxiv": "2609.12345"},
        source_urls={"arxiv": "https://arxiv.org/abs/2609.12345"},
        relevance_score=0.91,
        novelty_score=0.84,
        novelty_verdict="novel",
    )


def test_digest_store_round_trip_and_latest_date(tmp_path: object) -> None:
    store = DigestStore(tmp_path / "digest.db")
    paper = make_paper("paper:secure")
    store.save_digest(date(2026, 9, 18), [paper])

    assert store.count() == 1
    assert store.latest_date() == date(2026, 9, 18)
    assert store.available_dates() == [date(2026, 9, 18)]
    assert store.list_digest()[0].title == "Secure Agents"
    assert store.get_paper("paper:secure") == paper


def test_digest_store_updates_existing_canonical_paper(tmp_path: object) -> None:
    store = DigestStore(tmp_path / "digest.db")
    store.save_digest(date(2026, 9, 18), [make_paper("paper:secure")])
    store.save_digest(
        date(2026, 9, 19),
        [make_paper("paper:secure", title="Secure Agents — Revised")],
    )

    assert store.count() == 1
    assert store.latest_date() == date(2026, 9, 19)
    assert store.get_paper("paper:secure").title == "Secure Agents — Revised"
