from datetime import UTC, datetime
from types import SimpleNamespace

from backend.ingestion.arxiv_source import ArxivSource


def test_arxiv_entry_is_normalized_and_version_is_removed() -> None:
    entry = SimpleNamespace(
        entry_id="http://arxiv.org/abs/2609.12345v2",
        title="  Secure  Agents ",
        summary="We study tool-call security.",
        authors=[SimpleNamespace(name="Ada Lovelace")],
        published=datetime(2026, 9, 15, tzinfo=UTC),
    )

    paper = ArxivSource._to_record(entry)

    assert paper.source_ids == {"arxiv": "2609.12345"}
    assert paper.source_urls["arxiv"] == "https://arxiv.org/abs/2609.12345"
    assert paper.title == "Secure Agents"
    assert paper.authors == ["Ada Lovelace"]
