from datetime import date

from backend.ingestion.schema import PaperRecord
from backend.reconciliation.dedupe import PaperReconciler


def record(
    *,
    title: str,
    abstract: str,
    authors: list[str],
    published: date,
    source_ids: dict[str, str],
    source_urls: dict[str, str] | None = None,
    citation_count: int | None = None,
) -> PaperRecord:
    return PaperRecord(
        title=title,
        abstract=abstract,
        authors=authors,
        published_date=published,
        source_ids=source_ids,
        source_urls=source_urls or {},
        citation_count=citation_count,
        embedding=[1.0, 0.0],
        relevance_score=0.9,
    )


def test_shared_arxiv_id_merges_source_records_and_keeps_richest_data() -> None:
    arxiv = record(
        title="Secure Agents",
        abstract="A short abstract about secure agents.",
        authors=["Aazib Abdullah", "Ada Lovelace"],
        published=date(2026, 9, 1),
        source_ids={"arxiv": "2609.12345v2"},
        source_urls={"arxiv": "https://arxiv.org/abs/2609.12345"},
    )
    semantic_scholar = record(
        title="Secure Agents: Defending Tool Use",
        abstract=(
            "A substantially richer abstract about secure agents, tool execution, "
            "prompt injection attacks, evaluation, and mitigations."
        ),
        authors=["Aazib Abdullah", "Ada Lovelace"],
        published=date(2026, 9, 3),
        source_ids={"semantic_scholar": "S2-1", "arxiv": "2609.12345"},
        source_urls={"semantic_scholar": "https://example.test/s2"},
        citation_count=12,
    )

    result = PaperReconciler().reconcile([arxiv, semantic_scholar])

    assert result.input_count == 2
    assert result.merged_count == 1
    assert len(result.papers) == 1
    merged = result.papers[0]
    assert merged.canonical_id is not None and merged.canonical_id.startswith("paper:")
    assert merged.abstract == semantic_scholar.abstract
    assert merged.published_date == date(2026, 9, 1)
    assert merged.citation_count == 12
    assert merged.source_ids["arxiv"] == "2609.12345"
    assert merged.source_ids["semantic_scholar"] == "S2-1"
    assert set(merged.source_urls) == {"arxiv", "semantic_scholar"}
    assert merged.reconciliation_evidence[0].matched_by == "shared_identifier"


def test_near_title_author_overlap_and_date_window_enable_fuzzy_match() -> None:
    left = record(
        title="Robust Agents: Defending Against Prompt Injection",
        abstract="First source abstract with adequate detail.",
        authors=["Alice Smith", "Bob Jones"],
        published=date(2026, 9, 1),
        source_ids={"arxiv": "2609.10001"},
    )
    right = record(
        title="Robust Agents - Defending Against Prompt-Injection Attacks",
        abstract="Second source abstract with adequate detail.",
        authors=["A. Smith", "Robert Jones"],
        published=date(2026, 9, 5),
        source_ids={"openalex": "W10001"},
    )

    result = PaperReconciler().reconcile([left, right])

    assert result.merged_count == 1
    evidence = result.papers[0].reconciliation_evidence[0]
    assert evidence.matched_by == "fuzzy_metadata"
    assert evidence.author_overlap == 1.0
    assert evidence.publication_date_delta_days == 4


def test_similar_titles_do_not_merge_without_author_and_date_support() -> None:
    base = record(
        title="Adversarial Learning for Secure Models",
        abstract="First detailed abstract.",
        authors=["Alice Smith"],
        published=date(2025, 1, 1),
        source_ids={"arxiv": "2501.00001"},
    )
    different_author = record(
        title="Adversarial Learning for Secure Models",
        abstract="Second detailed abstract.",
        authors=["Carol Garcia"],
        published=date(2025, 1, 2),
        source_ids={"openalex": "W2"},
    )
    distant_date = record(
        title="Adversarial Learning for Secure Models",
        abstract="Third detailed abstract.",
        authors=["Alice Smith"],
        published=date(2026, 1, 1),
        source_ids={"semantic_scholar": "S2-3"},
    )
    expanded_title = record(
        title="Adversarial Learning: A Comprehensive Survey of Methods and Applications",
        abstract="Fourth detailed abstract.",
        authors=["Alice Smith"],
        published=date(2025, 1, 3),
        source_ids={"openalex": "W4"},
    )

    result = PaperReconciler().reconcile([base, different_author, distant_date, expanded_title])

    assert result.merged_count == 0
    assert len(result.papers) == 4
