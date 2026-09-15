# ArXiv Sentinel

ArXiv Sentinel is an autonomous research-monitoring agent for adversarial machine
learning and AI security. It discovers newly published work from arXiv, Semantic
Scholar, and OpenAlex, normalizes every result into one schema, and makes the final
relevance decision with semantic embeddings rather than keyword rules.

This repository currently contains the Phase 1 and Phase 2 vertical slices:

- adapters for all three research sources;
- a shared, validated `PaperRecord` contract;
- local sentence-transformer embeddings and reference-set relevance scoring;
- a fault-isolated async pipeline and runnable CLI;
- persistent Chroma memory with cosine nearest-neighbor retrieval;
- explainable novelty verdicts with links to the closest prior papers;
- deterministic tests for normalization, relevance, and novelty judgment.

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

The first pipeline run downloads the configured sentence-transformer model. Semantic
Scholar uses its keyless public endpoint; rate limits are retried briefly and then
isolated from the other sources. Set `OPENALEX_MAILTO` so OpenAlex can identify the
client.

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
       Chroma nearest-neighbor memory
                  |
                  v
    novelty verdict + closest-paper evidence
                  |
                  v
          enriched JSON / terminal digest
```

## Configuration

See `.env.example`. Secrets are ignored from the first commit. Phases 1 and 2 do not
require Gemini or any scholar API key. `GEMINI_API_KEY` is reserved for grounded
summarization and RAG in Phase 3.

Novelty is measured as `1 - highest prior-paper cosine similarity` and classified
with configurable defaults:

- similarity at least `0.92`: `duplicate`;
- similarity from `0.75` to `0.92`: `incremental`;
- similarity below `0.75`: `novel`.

Every result includes its closest prior papers and their similarities so the verdict
can be inspected. Relevant papers are stored immediately after assessment, allowing
the pipeline to catch duplicates within the same run as well as across days.

## Roadmap

- Phase 3: Gemini tool use, grounded summaries, and grounding verification.
- Phase 4: cross-source identity reconciliation.
- Phase 5: FastAPI digest/Q&A endpoints and the Next.js dashboard.
- Phase 6: scheduled ingestion after persistence/deployment decisions are settled.
