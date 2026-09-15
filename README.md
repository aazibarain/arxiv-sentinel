# ArXiv Sentinel

ArXiv Sentinel is an autonomous research-monitoring agent for adversarial machine
learning and AI security. It discovers newly published work from arXiv, Semantic
Scholar, and OpenAlex, normalizes every result into one schema, and makes the final
relevance decision with semantic embeddings rather than keyword rules.

This repository currently contains the Phase 1 vertical slice:

- adapters for all three research sources;
- a shared, validated `PaperRecord` contract;
- local sentence-transformer embeddings and reference-set relevance scoring;
- a fault-isolated async pipeline and runnable CLI;
- deterministic unit tests for normalization and semantic filtering.

Discovery queries are intentionally broad. They control how much material each
source returns, but they do **not** decide relevance. The local embedding model does
that by comparing each abstract with a curated AI-security reference set.

## Quick start

Python 3.11-3.13 is recommended because ML package support can lag behind brand-new
Python releases.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
pytest
python -m backend.pipeline --date 2026-09-15 --limit-per-source 50
```

The first pipeline run downloads the configured sentence-transformer model. Set
`SEMANTIC_SCHOLAR_API_KEY` for higher Semantic Scholar limits and
`OPENALEX_MAILTO` so OpenAlex can identify the client.

Useful CLI options:

```bash
python -m backend.pipeline --help
python -m backend.pipeline --date 2026-09-15 --json
python -m backend.pipeline --threshold 0.45 --limit-per-source 100
```

## Current architecture

```text
arXiv / Semantic Scholar / OpenAlex
                  |
                  v
         shared PaperRecord schema
                  |
                  v
   local sentence-transformer embeddings
                  |
                  v
       max similarity to topic references
                  |
                  v
          filtered JSON / terminal digest
```

## Configuration

See `.env.example`. Secrets are ignored from the first commit. Phase 1 does not
require Gemini; `GEMINI_API_KEY` is reserved for the grounded summarization and RAG
phases.

## Roadmap

- Phase 2: persistent Chroma memory and novelty verdicts.
- Phase 3: Gemini tool use, grounded summaries, and grounding verification.
- Phase 4: cross-source identity reconciliation.
- Phase 5: FastAPI digest/Q&A endpoints and the Next.js dashboard.
- Phase 6: scheduled ingestion after persistence/deployment decisions are settled.
