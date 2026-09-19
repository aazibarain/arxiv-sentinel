"""FastAPI application shell; digest endpoints arrive in Phase 5."""

from fastapi import FastAPI

app = FastAPI(title="ArXiv Sentinel API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "grounded-agent-summarization"}
