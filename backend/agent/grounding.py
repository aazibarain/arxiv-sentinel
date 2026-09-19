"""Programmatic verification for citation-grounded summaries."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from backend.agent.summarizer import GroundedSummary
from backend.ingestion.schema import normalize_whitespace


def _normalize(value: str) -> str:
    return normalize_whitespace(value).casefold()


def _sentences(value: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalize_whitespace(value))
        if len(sentence.split()) >= 4
    ]


@dataclass(frozen=True)
class GroundingReport:
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


class GroundingValidator:
    """Require every output claim to trace to the supplied abstract."""

    def __init__(
        self,
        *,
        span_similarity_threshold: float = 0.90,
        claim_coverage_threshold: float = 0.70,
    ) -> None:
        if not 0.0 <= span_similarity_threshold <= 1.0:
            raise ValueError("span_similarity_threshold must be between 0 and 1")
        if not 0.0 <= claim_coverage_threshold <= 1.0:
            raise ValueError("claim_coverage_threshold must be between 0 and 1")
        self.span_similarity_threshold = span_similarity_threshold
        self.claim_coverage_threshold = claim_coverage_threshold

    def validate(self, output: GroundedSummary, abstract: str) -> GroundingReport:
        errors: list[str] = []
        if not output.citations:
            return GroundingReport(("At least one grounded citation is required.",))

        abstract_normalized = _normalize(abstract)
        combined_output = normalize_whitespace(f"{output.summary} {output.why_it_matters}")
        combined_normalized = _normalize(combined_output)

        for index, citation in enumerate(output.citations, start=1):
            span = _normalize(citation.source_span)
            claim = _normalize(citation.claim)
            if len(span.split()) < 4:
                errors.append(f"Citation {index} source span is too short.")
            elif span not in abstract_normalized:
                similarity = fuzz.partial_ratio(span, abstract_normalized) / 100.0
                if similarity < self.span_similarity_threshold:
                    errors.append(
                        f"Citation {index} source span is not supported by the abstract "
                        f"(similarity={similarity:.2f})."
                    )
            if claim not in combined_normalized:
                coverage = fuzz.partial_ratio(claim, combined_normalized) / 100.0
                if coverage < self.claim_coverage_threshold:
                    errors.append(f"Citation {index} claim is absent from the generated text.")

        claims = [_normalize(citation.claim) for citation in output.citations]
        for sentence in _sentences(combined_output):
            normalized_sentence = _normalize(sentence)
            coverage = max(
                (
                    max(
                        fuzz.partial_ratio(normalized_sentence, claim),
                        fuzz.token_set_ratio(normalized_sentence, claim),
                    )
                    / 100.0
                    for claim in claims
                ),
                default=0.0,
            )
            if coverage < self.claim_coverage_threshold:
                errors.append(f"Generated sentence lacks a matching citation claim: {sentence}")

        return GroundingReport(tuple(errors))


class GroundingError(RuntimeError):
    """Raised after Gemini repeatedly returns an unsupported summary."""
