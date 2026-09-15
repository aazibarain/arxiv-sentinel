"""Lazy local sentence-transformer wrapper."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class TextEmbedder(Protocol):
    """Small interface that keeps relevance logic independently testable."""

    def embed(self, texts: Sequence[str]) -> NDArray[np.float32]: ...


class SentenceTransformerEmbedder:
    """CPU-friendly local embedding model loaded only on first use."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None

    def embed(self, texts: Sequence[str]) -> NDArray[np.float32]:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - depends on local setup
                raise RuntimeError("Install requirements.txt to enable semantic filtering") from exc
            self._model = SentenceTransformer(self.model_name, device="cpu")

        vectors = self._model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)
