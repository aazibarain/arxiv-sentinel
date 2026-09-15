"""Source-neutral paper schema used throughout the pipeline."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def normalize_whitespace(value: str) -> str:
    """Collapse source formatting whitespace without changing content."""

    return re.sub(r"\s+", " ", value).strip()


class SummaryCitation(BaseModel):
    """A generated claim and the exact source text used to support it."""

    claim: str
    source_span: str


class PaperRecord(BaseModel):
    """Canonical contract between ingestion and all downstream phases.

    ``canonical_id`` is absent during ingestion and assigned after reconciliation.
    This is intentionally optional even though the final stored record requires it.
    """

    canonical_id: str | None = None
    title: str = Field(min_length=1)
    abstract: str = Field(min_length=1)
    authors: list[str]
    published_date: date
    source_ids: dict[str, str] = Field(default_factory=dict)
    source_urls: dict[str, str] = Field(default_factory=dict)
    citation_count: int | None = Field(default=None, ge=0)
    embedding: list[float] | None = None
    relevance_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    novelty_score: float | None = Field(default=None, ge=0.0, le=1.0)
    novelty_verdict: Literal["novel", "incremental", "duplicate"] | None = None
    summary: str | None = None
    summary_citations: list[SummaryCitation] = Field(default_factory=list)
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("title", "abstract")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return normalize_whitespace(value)

    @field_validator("authors")
    @classmethod
    def clean_authors(cls, values: list[str]) -> list[str]:
        return [cleaned for value in values if (cleaned := normalize_whitespace(value))]

    @field_validator("source_ids", "source_urls")
    @classmethod
    def remove_empty_mapping_values(cls, values: dict[str, str]) -> dict[str, str]:
        return {key: value for key, value in values.items() if value}
