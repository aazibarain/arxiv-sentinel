from datetime import date

from backend.ingestion.schema import PaperRecord


def test_paper_record_normalizes_source_text() -> None:
    paper = PaperRecord(
        title="  A   useful\n title ",
        abstract="An abstract\nwith   source formatting.",
        authors=[" Ada   Lovelace ", "", " Grace Hopper"],
        published_date=date(2026, 9, 15),
        source_ids={"arxiv": "2609.12345", "doi": ""},
        source_urls={"arxiv": "https://arxiv.org/abs/2609.12345"},
    )

    assert paper.canonical_id is None
    assert paper.title == "A useful title"
    assert paper.abstract == "An abstract with source formatting."
    assert paper.authors == ["Ada Lovelace", "Grace Hopper"]
    assert paper.source_ids == {"arxiv": "2609.12345"}
