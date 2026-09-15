"""Explainable novelty decisions against persistent paper memory."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from backend.ingestion.schema import PaperRecord
from backend.memory.vector_store import PaperMemory


@dataclass(frozen=True)
class NoveltyThresholds:
    incremental: float = 0.75
    duplicate: float = 0.92

    def __post_init__(self) -> None:
        if not 0.0 <= self.incremental < self.duplicate <= 1.0:
            raise ValueError("novelty thresholds must satisfy 0 <= incremental < duplicate <= 1")


class NoveltyDetector:
    """Classify papers and immediately add each result to memory."""

    def __init__(
        self,
        memory: PaperMemory,
        *,
        thresholds: NoveltyThresholds | None = None,
        top_k: int = 5,
    ) -> None:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        self.memory = memory
        self.thresholds = thresholds or NoveltyThresholds()
        self.top_k = top_k

    def assess(self, paper: PaperRecord) -> PaperRecord:
        """Annotate one paper without mutating memory."""

        if paper.embedding is None:
            raise ValueError("paper must have an embedding before novelty analysis")
        matches = self.memory.query_similar(paper.embedding, k=self.top_k)
        max_similarity = max((match.similarity for match in matches), default=0.0)
        paper.novelty_matches = matches
        paper.novelty_score = 1.0 - max_similarity

        if max_similarity >= self.thresholds.duplicate:
            paper.novelty_verdict = "duplicate"
        elif max_similarity >= self.thresholds.incremental:
            paper.novelty_verdict = "incremental"
        else:
            paper.novelty_verdict = "novel"
        return paper

    def process(self, papers: Sequence[PaperRecord]) -> list[PaperRecord]:
        """Assess and store papers sequentially so same-run duplicates are detected."""

        processed = []
        for paper in papers:
            self.assess(paper)
            self.memory.upsert([paper])
            processed.append(paper)
        return processed
