"""FastAPI application for digests, paper details, and grounded corpus Q&A."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.agent.qa import CorpusQA, GroundedAnswer
from backend.config import get_settings
from backend.db.models import DigestStore
from backend.filtering.embed import SentenceTransformerEmbedder
from backend.ingestion.schema import PaperRecord


class AskRequest(BaseModel):
    question: str = Field(min_length=4, max_length=1000)


class DigestResponse(BaseModel):
    date: date | None
    available_dates: list[date]
    count: int
    papers: list[dict[str, object]]


app = FastAPI(
    title="ArXiv Sentinel API",
    version="0.5.0",
    description="Explainable monitoring and grounded Q&A for AI-security research.",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _public_paper(paper: PaperRecord) -> dict[str, object]:
    """Keep large embedding vectors inside the retrieval layer, not API responses."""

    return paper.model_dump(mode="json", exclude={"embedding"})


def _seed_if_empty(store: DigestStore) -> None:
    if store.count():
        return
    seed_path = Path(__file__).parent / "db" / "seed_digest.json"
    if not seed_path.exists():
        return
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    papers = [PaperRecord.model_validate(item) for item in payload["papers"]]
    store.save_digest(date.fromisoformat(payload["digest_date"]), papers)


@lru_cache
def get_digest_store() -> DigestStore:
    store = DigestStore(settings.digest_db_path)
    _seed_if_empty(store)
    return store


@lru_cache
def get_qa_agent() -> CorpusQA:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return CorpusQA(
        embedder=SentenceTransformerEmbedder(settings.embedding_model),
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        top_k=settings.qa_top_k,
        max_attempts=settings.qa_max_attempts,
    )


@app.get("/health")
def health(store: Annotated[DigestStore, Depends(get_digest_store)]) -> dict[str, str | int]:
    return {
        "status": "ok",
        "phase": "dashboard-and-grounded-rag",
        "paper_count": store.count(),
    }


@app.get("/digest", response_model=DigestResponse)
def digest(
    store: Annotated[DigestStore, Depends(get_digest_store)],
    digest_date: Annotated[date | None, Query(alias="date")] = None,
) -> DigestResponse:
    selected_date = digest_date or store.latest_date()
    papers = store.list_digest(selected_date)
    return DigestResponse(
        date=selected_date,
        available_dates=store.available_dates(),
        count=len(papers),
        papers=[_public_paper(paper) for paper in papers],
    )


@app.get("/paper/{canonical_id:path}")
def paper_detail(
    canonical_id: str,
    store: Annotated[DigestStore, Depends(get_digest_store)],
) -> dict[str, object]:
    paper = store.get_paper(canonical_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return _public_paper(paper)


@app.post("/ask", response_model=GroundedAnswer)
async def ask(
    request: AskRequest,
    store: Annotated[DigestStore, Depends(get_digest_store)],
) -> GroundedAnswer:
    papers = store.list_all()
    if not papers:
        raise HTTPException(status_code=503, detail="The research corpus is empty")
    try:
        agent = get_qa_agent()
        return await asyncio.to_thread(agent.ask, request.question, papers)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
