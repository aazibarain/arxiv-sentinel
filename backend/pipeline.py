"""Daily pipeline: discover, filter, judge novelty, and remember papers."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from backend.config import Settings, get_settings
from backend.filtering.embed import SentenceTransformerEmbedder
from backend.filtering.relevance import RelevanceFilter
from backend.ingestion.arxiv_source import ArxivSource
from backend.ingestion.base import PaperSource
from backend.ingestion.openalex_source import OpenAlexSource
from backend.ingestion.schema import PaperRecord
from backend.ingestion.semantic_scholar_source import SemanticScholarSource
from backend.memory.novelty import NoveltyDetector, NoveltyThresholds
from backend.memory.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PhaseOneResult:
    target_date: date
    candidates: list[PaperRecord]
    relevant: list[PaperRecord]
    source_counts: dict[str, int]
    source_errors: dict[str, str]


@dataclass(frozen=True)
class PhaseTwoResult(PhaseOneResult):
    memory_count_before: int
    memory_count_after: int


def build_sources(settings: Settings) -> list[PaperSource]:
    """Create the production source adapters from environment settings."""

    return [
        ArxivSource(timeout_seconds=settings.source_request_timeout_seconds),
        SemanticScholarSource(
            timeout_seconds=settings.source_request_timeout_seconds,
        ),
        OpenAlexSource(
            mailto=settings.openalex_mailto,
            timeout_seconds=settings.source_request_timeout_seconds,
        ),
    ]


async def fetch_candidates(
    sources: list[PaperSource],
    target_date: date,
    *,
    limit_per_source: int,
) -> tuple[list[PaperRecord], dict[str, int], dict[str, str]]:
    """Fetch providers concurrently and isolate a failing provider from the others."""

    end_date = target_date + timedelta(days=1)
    results = await asyncio.gather(
        *(source.fetch(target_date, end_date, limit=limit_per_source) for source in sources),
        return_exceptions=True,
    )
    candidates: list[PaperRecord] = []
    counts: dict[str, int] = {}
    errors: dict[str, str] = {}

    for source, result in zip(sources, results, strict=True):
        if isinstance(result, BaseException):
            counts[source.name] = 0
            errors[source.name] = str(result)
            logger.warning("%s failed: %s", source.name, result)
            continue
        counts[source.name] = len(result)
        candidates.extend(result)
    return candidates, counts, errors


async def run_phase_one(
    target_date: date,
    *,
    limit_per_source: int = 50,
    threshold: float | None = None,
    settings: Settings | None = None,
    sources: list[PaperSource] | None = None,
    relevance_filter: RelevanceFilter | None = None,
) -> PhaseOneResult:
    """Execute the first complete pipeline slice for one publication date."""

    if limit_per_source < 1:
        raise ValueError("limit_per_source must be positive")
    settings = settings or get_settings()
    sources = sources or build_sources(settings)
    candidates, counts, errors = await fetch_candidates(
        sources,
        target_date,
        limit_per_source=limit_per_source,
    )
    if relevance_filter is None:
        relevance_filter = RelevanceFilter(
            SentenceTransformerEmbedder(settings.embedding_model),
            threshold=settings.relevance_threshold if threshold is None else threshold,
        )
    relevant = await asyncio.to_thread(relevance_filter.filter, candidates)
    relevant.sort(key=lambda paper: paper.relevance_score or -1.0, reverse=True)
    return PhaseOneResult(target_date, candidates, relevant, counts, errors)


def build_novelty_detector(settings: Settings) -> NoveltyDetector:
    memory = ChromaVectorStore(
        settings.chroma_path,
        collection_name=settings.chroma_collection,
    )
    return NoveltyDetector(
        memory,
        thresholds=NoveltyThresholds(
            incremental=settings.novelty_incremental_threshold,
            duplicate=settings.novelty_duplicate_threshold,
        ),
        top_k=settings.novelty_top_k,
    )


async def run_pipeline(
    target_date: date,
    *,
    limit_per_source: int = 50,
    threshold: float | None = None,
    settings: Settings | None = None,
    sources: list[PaperSource] | None = None,
    relevance_filter: RelevanceFilter | None = None,
    novelty_detector: NoveltyDetector | None = None,
) -> PhaseTwoResult:
    """Execute ingestion, relevance filtering, novelty analysis, and persistence."""

    settings = settings or get_settings()
    phase_one = await run_phase_one(
        target_date,
        limit_per_source=limit_per_source,
        threshold=threshold,
        settings=settings,
        sources=sources,
        relevance_filter=relevance_filter,
    )
    if novelty_detector is None:
        novelty_detector = await asyncio.to_thread(build_novelty_detector, settings)
    memory_before = await asyncio.to_thread(novelty_detector.memory.count)
    processed = await asyncio.to_thread(novelty_detector.process, phase_one.relevant)
    memory_after = await asyncio.to_thread(novelty_detector.memory.count)
    return PhaseTwoResult(
        target_date=phase_one.target_date,
        candidates=phase_one.candidates,
        relevant=processed,
        source_counts=phase_one.source_counts,
        source_errors=phase_one.source_errors,
        memory_count_before=memory_before,
        memory_count_after=memory_after,
    )


def result_as_dict(result: PhaseOneResult | PhaseTwoResult) -> dict[str, Any]:
    payload = {
        "target_date": result.target_date.isoformat(),
        "candidate_count": len(result.candidates),
        "relevant_count": len(result.relevant),
        "source_counts": result.source_counts,
        "source_errors": result.source_errors,
        "papers": [paper.model_dump(mode="json") for paper in result.relevant],
    }
    if isinstance(result, PhaseTwoResult):
        payload["memory_count_before"] = result.memory_count_before
        payload["memory_count_after"] = result.memory_count_after
    return payload


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        type=_parse_date,
        default=datetime.now(UTC).date(),
        help="publication date to process (YYYY-MM-DD, default: today in UTC)",
    )
    parser.add_argument("--limit-per-source", type=int, default=50)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def _print_human(result: PhaseOneResult | PhaseTwoResult) -> None:
    print(f"ArXiv Sentinel digest for {result.target_date.isoformat()}")
    print(f"Candidates: {len(result.candidates)} | Relevant: {len(result.relevant)}")
    source_summary = ", ".join(f"{name}={count}" for name, count in result.source_counts.items())
    print("Sources: " + source_summary)
    if isinstance(result, PhaseTwoResult):
        print(f"Memory: {result.memory_count_before} -> {result.memory_count_after} papers")
    for name, error in result.source_errors.items():
        print(f"Warning: {name}: {error}")
    for index, paper in enumerate(result.relevant, start=1):
        sources = ", ".join(sorted(paper.source_ids))
        novelty = (
            f" | {paper.novelty_verdict} ({paper.novelty_score:.3f})"
            if paper.novelty_verdict and paper.novelty_score is not None
            else ""
        )
        print(f"\n{index}. [relevance {paper.relevance_score:.3f}{novelty}] {paper.title}")
        print(f"   {', '.join(paper.authors)} | {sources}")
        if paper.novelty_matches:
            closest = paper.novelty_matches[0]
            print(f"   Closest prior paper: {closest.title} ({closest.similarity:.3f})")


def main() -> None:
    args = _build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = asyncio.run(
        run_pipeline(
            args.date,
            limit_per_source=args.limit_per_source,
            threshold=args.threshold,
        )
    )
    if args.json:
        print(json.dumps(result_as_dict(result), indent=2))
    else:
        _print_human(result)


if __name__ == "__main__":
    main()
