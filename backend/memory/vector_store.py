"""Persistent Chroma storage for relevant paper embeddings."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from backend.ingestion.schema import PaperRecord, SimilarPaper, normalize_whitespace


class PaperMemory(Protocol):
    """Storage contract consumed by novelty detection and later RAG tools."""

    def count(self) -> int: ...

    def query_similar(self, embedding: Sequence[float], *, k: int) -> list[SimilarPaper]: ...

    def upsert(self, papers: Sequence[PaperRecord]) -> None: ...


def memory_id_for(paper: PaperRecord) -> str:
    """Return a stable identifier before Phase 4 assigns a canonical ID."""

    if paper.canonical_id:
        return paper.canonical_id
    for source in ("arxiv", "doi", "semantic_scholar", "openalex"):
        if source_id := paper.source_ids.get(source):
            return f"{source}:{source_id.lower()}"
    identity = f"{normalize_whitespace(paper.title).lower()}|{paper.published_date.isoformat()}"
    return "paper:" + hashlib.sha256(identity.encode()).hexdigest()[:24]


def _metadata_for(paper: PaperRecord) -> dict[str, str | int | float | bool]:
    metadata: dict[str, str | int | float | bool] = {
        "title": paper.title,
        "authors_json": json.dumps(paper.authors, ensure_ascii=False),
        "published_date": paper.published_date.isoformat(),
        "source_ids_json": json.dumps(paper.source_ids, sort_keys=True),
        "source_urls_json": json.dumps(paper.source_urls, sort_keys=True),
        "ingested_at": paper.ingested_at.isoformat(),
    }
    if paper.relevance_score is not None:
        metadata["relevance_score"] = paper.relevance_score
    if paper.novelty_score is not None:
        metadata["novelty_score"] = paper.novelty_score
    if paper.novelty_verdict is not None:
        metadata["novelty_verdict"] = paper.novelty_verdict
    if paper.citation_count is not None:
        metadata["citation_count"] = paper.citation_count
    if paper.summary is not None:
        metadata["summary"] = paper.summary
    if paper.why_it_matters is not None:
        metadata["why_it_matters"] = paper.why_it_matters
    if paper.summary_citations:
        metadata["summary_citations_json"] = json.dumps(
            [citation.model_dump(mode="json") for citation in paper.summary_citations],
            ensure_ascii=False,
        )
    return metadata


class ChromaVectorStore:
    """Chroma-backed local paper memory using caller-supplied embeddings."""

    def __init__(
        self,
        path: str | Path,
        *,
        collection_name: str = "arxiv_sentinel_papers",
        client: Any | None = None,
    ) -> None:
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - depends on local setup
            raise RuntimeError("Install requirements.txt to enable persistent memory") from exc

        Path(path).mkdir(parents=True, exist_ok=True)
        self.client = client or chromadb.PersistentClient(path=str(path))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
        )

    def count(self) -> int:
        return self.collection.count()

    def query_similar(self, embedding: Sequence[float], *, k: int) -> list[SimilarPaper]:
        if k < 1:
            raise ValueError("k must be positive")
        memory_size = self.count()
        if memory_size == 0:
            return []
        result = self.collection.query(
            query_embeddings=[list(embedding)],
            n_results=min(k, memory_size),
            include=["metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        matches = []
        for record_id, metadata, distance in zip(ids, metadatas, distances, strict=True):
            metadata = metadata or {}
            matches.append(
                SimilarPaper(
                    memory_id=record_id,
                    title=str(metadata.get("title", "Unknown paper")),
                    published_date=str(metadata["published_date"]),
                    similarity=max(0.0, min(1.0, 1.0 - float(distance))),
                    source_ids=json.loads(str(metadata.get("source_ids_json", "{}"))),
                    source_urls=json.loads(str(metadata.get("source_urls_json", "{}"))),
                )
            )
        matches.sort(key=lambda match: match.similarity, reverse=True)
        return matches

    def upsert(self, papers: Sequence[PaperRecord]) -> None:
        if not papers:
            return
        missing = [paper.title for paper in papers if paper.embedding is None]
        if missing:
            raise ValueError(f"cannot store papers without embeddings: {missing}")
        self.collection.upsert(
            ids=[memory_id_for(paper) for paper in papers],
            embeddings=[paper.embedding for paper in papers],
            documents=[paper.abstract for paper in papers],
            metadatas=[_metadata_for(paper) for paper in papers],
        )
