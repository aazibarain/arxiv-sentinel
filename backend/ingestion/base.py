"""Shared interfaces and errors for source adapters."""

from datetime import date
from typing import Protocol

from backend.ingestion.schema import PaperRecord


class SourceFetchError(RuntimeError):
    """Raised when a research source cannot produce a valid response."""


class PaperSource(Protocol):
    """Interface implemented by every source adapter."""

    name: str

    async def fetch(
        self,
        start_date: date,
        end_date: date,
        *,
        limit: int,
    ) -> list[PaperRecord]: ...
