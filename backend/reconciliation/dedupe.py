"""Explainable matching and merging for cross-source paper records."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass

from rapidfuzz import fuzz

from backend.ingestion.schema import PaperRecord, ReconciliationEvidence


@dataclass(frozen=True)
class ReconciliationResult:
    papers: list[PaperRecord]
    input_count: int
    merged_count: int


def _normalized_identifier(source: str, value: str) -> str:
    normalized = value.strip().casefold()
    if source == "arxiv":
        normalized = re.sub(r"v\d+$", "", normalized)
    if source == "doi":
        normalized = normalized.removeprefix("https://doi.org/")
    return normalized


def _identifier_set(paper: PaperRecord) -> set[tuple[str, str]]:
    return {
        (source, _normalized_identifier(source, value))
        for source, value in paper.source_ids.items()
        if value.strip()
    }


def _normalized_title(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", title.casefold()))


def _author_surnames(authors: Sequence[str]) -> set[str]:
    surnames = set()
    for author in authors:
        tokens = re.findall(r"[a-z0-9]+", author.casefold())
        if tokens:
            surnames.add(tokens[-1])
    return surnames


def _author_overlap(left: PaperRecord, right: PaperRecord) -> float:
    left_authors = _author_surnames(left.authors)
    right_authors = _author_surnames(right.authors)
    if not left_authors or not right_authors:
        return 0.0
    return len(left_authors & right_authors) / min(len(left_authors), len(right_authors))


def _title_similarity(left: PaperRecord, right: PaperRecord) -> float:
    return (
        fuzz.token_sort_ratio(
            _normalized_title(left.title),
            _normalized_title(right.title),
        )
        / 100.0
    )


class PaperReconciler:
    """Cluster source records using identifiers first, then conservative fuzzy rules."""

    def __init__(
        self,
        *,
        title_similarity_threshold: float = 0.90,
        author_overlap_threshold: float = 0.50,
        date_window_days: int = 30,
    ) -> None:
        if not 0.0 <= title_similarity_threshold <= 1.0:
            raise ValueError("title_similarity_threshold must be between 0 and 1")
        if not 0.0 <= author_overlap_threshold <= 1.0:
            raise ValueError("author_overlap_threshold must be between 0 and 1")
        if date_window_days < 0:
            raise ValueError("date_window_days cannot be negative")
        self.title_similarity_threshold = title_similarity_threshold
        self.author_overlap_threshold = author_overlap_threshold
        self.date_window_days = date_window_days

    def reconcile(self, papers: Sequence[PaperRecord]) -> ReconciliationResult:
        if not papers:
            return ReconciliationResult([], 0, 0)

        parents = list(range(len(papers)))
        evidence: list[tuple[int, int, ReconciliationEvidence]] = []

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        for left_index, left in enumerate(papers):
            for right_index in range(left_index + 1, len(papers)):
                right = papers[right_index]
                match = self._match(left, right)
                if match is not None:
                    union(left_index, right_index)
                    evidence.append((left_index, right_index, match))

        groups: dict[int, list[int]] = {}
        for index in range(len(papers)):
            groups.setdefault(find(index), []).append(index)

        reconciled = []
        for indices in groups.values():
            records = [papers[index] for index in indices]
            group_evidence = [
                match
                for left_index, right_index, match in evidence
                if left_index in indices and right_index in indices
            ]
            reconciled.append(_merge_records(records, group_evidence))

        return ReconciliationResult(
            papers=reconciled,
            input_count=len(papers),
            merged_count=len(papers) - len(reconciled),
        )

    def _match(
        self,
        left: PaperRecord,
        right: PaperRecord,
    ) -> ReconciliationEvidence | None:
        title_similarity = _title_similarity(left, right)
        author_overlap = _author_overlap(left, right)
        date_delta = abs((left.published_date - right.published_date).days)
        shared_identifier = bool(_identifier_set(left) & _identifier_set(right))

        if shared_identifier:
            matched_by = "shared_identifier"
        elif (
            title_similarity >= self.title_similarity_threshold
            and author_overlap >= self.author_overlap_threshold
            and date_delta <= self.date_window_days
        ):
            matched_by = "fuzzy_metadata"
        else:
            return None

        return ReconciliationEvidence(
            left_source_ids=left.source_ids,
            right_source_ids=right.source_ids,
            matched_by=matched_by,
            title_similarity=title_similarity,
            author_overlap=author_overlap,
            publication_date_delta_days=date_delta,
        )


def _merge_records(
    records: Sequence[PaperRecord],
    evidence: list[ReconciliationEvidence],
) -> PaperRecord:
    primary = max(
        records,
        key=lambda paper: (
            len(paper.abstract),
            paper.citation_count or 0,
            len(paper.authors),
        ),
    )
    merged = primary.model_copy(deep=True)
    merged.canonical_id = _canonical_id(records)
    merged.published_date = min(paper.published_date for paper in records)
    merged.ingested_at = min(paper.ingested_at for paper in records)
    merged.source_ids = _merged_mapping(records, "source_ids", primary)
    merged.source_urls = _merged_mapping(records, "source_urls", primary)
    merged.authors = _merged_authors(records, primary)
    citation_counts = [
        paper.citation_count for paper in records if paper.citation_count is not None
    ]
    merged.citation_count = max(citation_counts) if citation_counts else None
    relevance_scores = [
        paper.relevance_score for paper in records if paper.relevance_score is not None
    ]
    merged.relevance_score = max(relevance_scores) if relevance_scores else None
    merged.reconciliation_evidence = evidence
    return merged


def _merged_mapping(
    records: Sequence[PaperRecord],
    field_name: str,
    primary: PaperRecord,
) -> dict[str, str]:
    merged: dict[str, str] = {}
    for paper in records:
        merged.update(getattr(paper, field_name))
    merged.update(getattr(primary, field_name))
    return merged


def _merged_authors(records: Sequence[PaperRecord], primary: PaperRecord) -> list[str]:
    merged = list(primary.authors)
    seen = {author.casefold() for author in merged}
    for paper in records:
        for author in paper.authors:
            if author.casefold() not in seen:
                merged.append(author)
                seen.add(author.casefold())
    return merged


def _canonical_id(records: Sequence[PaperRecord]) -> str:
    identifiers: dict[str, set[str]] = {}
    for paper in records:
        for source, value in paper.source_ids.items():
            identifiers.setdefault(source, set()).add(_normalized_identifier(source, value))

    for source in ("doi", "arxiv", "openalex", "semantic_scholar"):
        if values := identifiers.get(source):
            seed = f"{source}:{sorted(values)[0]}"
            return "paper:" + hashlib.sha256(seed.encode()).hexdigest()[:24]

    primary = min(records, key=lambda paper: paper.published_date)
    fallback = (
        f"{_normalized_title(primary.title)}|{primary.published_date.isoformat()}|"
        f"{'|'.join(sorted(_author_surnames(primary.authors)))}"
    )
    return "paper:" + hashlib.sha256(fallback.encode()).hexdigest()[:24]
