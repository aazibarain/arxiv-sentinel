"""Embedding-based relevance scoring against AI-security prototypes."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from backend.config import AI_SECURITY_REFERENCE_TOPICS
from backend.filtering.embed import TextEmbedder
from backend.ingestion.schema import PaperRecord


def _row_normalize(matrix: NDArray[np.float32]) -> NDArray[np.float32]:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, np.finfo(np.float32).eps)


class RelevanceFilter:
    """Score papers by their closest positive topic reference."""

    def __init__(
        self,
        embedder: TextEmbedder,
        *,
        threshold: float = 0.5,
        references: Sequence[str] = AI_SECURITY_REFERENCE_TOPICS,
    ) -> None:
        if not -1.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between -1 and 1")
        if not references:
            raise ValueError("at least one relevance reference is required")
        self.embedder = embedder
        self.threshold = threshold
        self.references = tuple(references)
        self._reference_embeddings: NDArray[np.float32] | None = None

    def filter(self, papers: Sequence[PaperRecord]) -> list[PaperRecord]:
        """Annotate every paper and return those meeting the configured threshold."""

        if not papers:
            return []
        if self._reference_embeddings is None:
            references = np.asarray(self.embedder.embed(self.references), dtype=np.float32)
            self._reference_embeddings = _row_normalize(references)

        abstracts = [paper.abstract for paper in papers]
        paper_embeddings = _row_normalize(
            np.asarray(self.embedder.embed(abstracts), dtype=np.float32)
        )
        if paper_embeddings.shape[1] != self._reference_embeddings.shape[1]:
            raise ValueError("paper and reference embeddings have different dimensions")

        similarity = paper_embeddings @ self._reference_embeddings.T
        relevance_scores = similarity.max(axis=1)

        relevant = []
        for paper, embedding, score in zip(
            papers, paper_embeddings, relevance_scores, strict=True
        ):
            paper.embedding = embedding.astype(float).tolist()
            paper.relevance_score = float(np.clip(score, -1.0, 1.0))
            if paper.relevance_score >= self.threshold:
                relevant.append(paper)
        return relevant
