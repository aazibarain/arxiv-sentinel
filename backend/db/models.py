"""Small SQLite repository for API-facing digest metadata.

Chroma remains the similarity index. SQLite keeps complete paper records so the
dashboard can list and inspect them without reaching into Chroma metadata.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from backend.ingestion.schema import PaperRecord


class DigestStore:
    """Persist complete paper records grouped by the day they were processed."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS papers (
                    canonical_id TEXT PRIMARY KEY,
                    digest_date TEXT NOT NULL,
                    published_date TEXT NOT NULL,
                    relevance_score REAL,
                    novelty_verdict TEXT,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_papers_digest_date "
                "ON papers(digest_date DESC, relevance_score DESC)"
            )

    def save_digest(self, digest_date: date, papers: Sequence[PaperRecord]) -> None:
        """Upsert one processed digest atomically."""

        rows = []
        for paper in papers:
            if not paper.canonical_id:
                raise ValueError("digest papers require a canonical_id")
            rows.append(
                (
                    paper.canonical_id,
                    digest_date.isoformat(),
                    paper.published_date.isoformat(),
                    paper.relevance_score,
                    paper.novelty_verdict,
                    paper.model_dump_json(),
                )
            )
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO papers (
                    canonical_id, digest_date, published_date,
                    relevance_score, novelty_verdict, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_id) DO UPDATE SET
                    digest_date = excluded.digest_date,
                    published_date = excluded.published_date,
                    relevance_score = excluded.relevance_score,
                    novelty_verdict = excluded.novelty_verdict,
                    payload_json = excluded.payload_json
                """,
                rows,
            )

    def list_digest(self, digest_date: date | None = None) -> list[PaperRecord]:
        """Return the requested digest, or the most recent available digest."""

        selected_date = digest_date or self.latest_date()
        if selected_date is None:
            return []
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM papers
                WHERE digest_date = ?
                ORDER BY relevance_score DESC, published_date DESC, canonical_id
                """,
                (selected_date.isoformat(),),
            ).fetchall()
        return [PaperRecord.model_validate(json.loads(row["payload_json"])) for row in rows]

    def list_all(self) -> list[PaperRecord]:
        """Return every canonical paper for corpus-wide Q&A."""

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM papers ORDER BY digest_date DESC, relevance_score DESC"
            ).fetchall()
        return [PaperRecord.model_validate(json.loads(row["payload_json"])) for row in rows]

    def get_paper(self, canonical_id: str) -> PaperRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM papers WHERE canonical_id = ?",
                (canonical_id,),
            ).fetchone()
        if row is None:
            return None
        return PaperRecord.model_validate(json.loads(row["payload_json"]))

    def latest_date(self) -> date | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT MAX(digest_date) AS digest_date FROM papers"
            ).fetchone()
        return date.fromisoformat(row["digest_date"]) if row and row["digest_date"] else None

    def available_dates(self) -> list[date]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT digest_date FROM papers ORDER BY digest_date DESC"
            ).fetchall()
        return [date.fromisoformat(row["digest_date"]) for row in rows]

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM papers").fetchone()
        return int(row["count"])
