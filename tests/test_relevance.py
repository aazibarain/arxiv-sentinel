from collections.abc import Sequence
from datetime import date

import numpy as np
from numpy.typing import NDArray

from backend.filtering.relevance import RelevanceFilter
from backend.ingestion.schema import PaperRecord


class MappingEmbedder:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.calls = 0

    def embed(self, texts: Sequence[str]) -> NDArray[np.float32]:
        self.calls += 1
        return np.asarray([self.vectors[text] for text in texts], dtype=np.float32)


def paper(title: str, abstract: str) -> PaperRecord:
    return PaperRecord(
        title=title,
        abstract=abstract,
        authors=["Researcher"],
        published_date=date(2026, 9, 15),
        source_ids={"arxiv": title},
        source_urls={"arxiv": "https://example.test"},
    )


def test_relevance_filter_scores_semantically_and_caches_references() -> None:
    vectors = {
        "AI security prototype": [1.0, 0.0],
        "A prompt injection attack against tool-using agents.": [0.9, 0.1],
        "A new telescope measures a distant galaxy.": [0.1, 0.9],
    }
    embedder = MappingEmbedder(vectors)
    relevance = RelevanceFilter(
        embedder,
        threshold=0.7,
        references=("AI security prototype",),
    )
    attack = paper("attack", "A prompt injection attack against tool-using agents.")
    astronomy = paper("astronomy", "A new telescope measures a distant galaxy.")

    selected = relevance.filter([attack, astronomy])
    relevance.filter([attack])

    assert selected == [attack]
    assert attack.relevance_score is not None and attack.relevance_score > 0.99
    assert astronomy.relevance_score is not None and astronomy.relevance_score < 0.2
    assert len(attack.embedding or []) == 2
    assert embedder.calls == 3  # references once, papers twice
