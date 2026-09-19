from datetime import date

from fastapi.testclient import TestClient

from backend.db.models import DigestStore
from backend.ingestion.schema import PaperRecord
from backend.main import app, get_digest_store


def test_digest_and_paper_endpoints(tmp_path: object) -> None:
    store = DigestStore(tmp_path / "api.db")
    paper = PaperRecord(
        canonical_id="paper:api",
        title="API Security Paper",
        abstract="A detailed abstract about agent security and prompt injection.",
        authors=["Ada Researcher"],
        published_date=date(2026, 9, 19),
        source_ids={"arxiv": "2609.99999"},
        source_urls={"arxiv": "https://arxiv.org/abs/2609.99999"},
        embedding=[1.0, 0.0],
        relevance_score=0.9,
    )
    store.save_digest(date(2026, 9, 19), [paper])
    app.dependency_overrides[get_digest_store] = lambda: store
    client = TestClient(app)

    digest = client.get("/digest?date=2026-09-19")
    detail = client.get("/paper/paper:api")
    missing = client.get("/paper/paper:missing")

    app.dependency_overrides.clear()
    assert digest.status_code == 200
    assert digest.json()["count"] == 1
    assert "embedding" not in digest.json()["papers"][0]
    assert detail.status_code == 200 and detail.json()["canonical_id"] == "paper:api"
    assert missing.status_code == 404
