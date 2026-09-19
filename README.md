# ArXiv Sentinel

ArXiv Sentinel is an autonomous research-monitoring agent for adversarial machine
learning and AI security. It discovers newly published work from arXiv, Semantic
Scholar, and OpenAlex, normalizes every result into one schema, and makes the final
relevance decision with semantic embeddings rather than keyword rules.

This repository contains the original local Python agent and the production web runtime:

- adapters for all three research sources;
- a shared, validated `PaperRecord` contract;
- local sentence-transformer embeddings and reference-set relevance scoring;
- a fault-isolated async pipeline and runnable CLI;
- persistent Chroma memory with cosine nearest-neighbor retrieval;
- explainable novelty verdicts with links to the closest prior papers;
- keyless Semantic Scholar and OpenAlex research tools;
- structured Gemini summaries with claim-to-abstract citations;
- a programmatic grounding gate that rejects and retries unsupported output;
- cross-source identity reconciliation with inspectable match evidence;
- deterministic tests for ingestion, relevance, reconciliation, novelty, tools, and grounding.
- SQLite-backed digest persistence with FastAPI digest, paper, and grounded Q&A endpoints;
- a responsive Next.js dashboard with topic search, inspectable paper evidence, and corpus chat;
- a Vercel-deployed agent that keeps Gemini and storage credentials server-side;
- durable daily digests and a rolling research corpus in Vercel Blob;
- scheduled ingestion through a protected Vercel Cron route;
- live dashboard, paper, digest, and grounded corpus-Q&A APIs; and
- explicit loading, empty, partial-source, and storage-error states.

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
# Add GEMINI_API_KEY to .env
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
python -m backend.pipeline --date 2026-09-15 --no-summaries
```

Run the Phase 5 applications locally in separate terminals:

```bash
uvicorn backend.main:app --reload --port 8000
cd frontend
npm install
npm run dev
```

The FastAPI docs are available at `http://localhost:8000/docs`; the dashboard is at
`http://localhost:3000`. The Python runtime persists locally to SQLite and Chroma. The deployed
Next.js runtime independently persists its live digest and rolling corpus in Vercel Blob; it does
not use the repository's historical demonstration fixture.

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
  identifier + title/author/date reconciliation
                  |
                  v
       Chroma nearest-neighbor memory
                  |
                  v
    novelty verdict + closest-paper evidence
                  |
                  v
  keyless citation and metadata enrichment
                  |
                  v
      Gemini structured summary generation
                  |
                  v
 programmatic claim/span grounding validation
                  |
                  v
 local: Chroma + SQLite / production: Vercel Blob
                  |
                  v
 FastAPI API / Next.js dashboard / grounded Q&A
```

## Configuration

See `.env.example`. Secrets are ignored from the first commit. No scholar API key is
used. `GEMINI_API_KEY` is read only from the environment for Phase 3 summaries and
must never be committed.

Novelty is measured as `1 - highest prior-paper cosine similarity` and classified
with configurable defaults:

- similarity at least `0.92`: `duplicate`;
- similarity from `0.75` to `0.92`: `incremental`;
- similarity below `0.75`: `novel`.

Every result includes its closest prior papers and their similarities so the verdict
can be inspected. Relevant papers are stored immediately after assessment, allowing
the pipeline to catch duplicates within the same run as well as across days.

For each novel or incremental paper, the agent gathers available citation and
OpenAlex context, then asks Gemini for structured `summary`, `why_it_matters`, and
claim/span citations. Code verifies that every cited span occurs in, or closely
matches, the supplied abstract and that every generated sentence maps to a citation
claim. Failed grounding is returned to Gemini for correction up to three times.
Duplicates are retained in memory but skipped for generation to conserve quota.

Before novelty analysis, records are reconciled across providers. Shared arXiv, DOI,
Semantic Scholar, or OpenAlex identifiers are decisive. Without a shared identifier,
the default rule requires at least `0.90` title similarity, `0.50` author-surname
overlap, and publication dates within 30 days. A merged record keeps the richest
abstract, earliest publication date, highest citation count, all source IDs and
URLs, and explicit evidence describing why the match was accepted.

## Phase 5 API

- `GET /digest?date=YYYY-MM-DD` returns the requested processed digest (or the latest).
- `GET /paper/{canonical_id}` returns one full record without its embedding vector.
- `POST /ask` retrieves semantically related papers, asks Gemini using only those
  abstracts, and rejects answers whose claims or source spans fail grounding validation.

The deployed Next.js application exposes live server routes backed by Vercel Blob. Its daily
cron collects up to the configured per-source limit, semantically ranks results, merges duplicate
records, summarizes the top digest papers, and updates the rolling corpus. Both summary and Q&A
generation require exact source spans; invalid structured output is retried and then replaced by
an explicitly labeled extractive fallback.

## Production operations

See `frontend/README.md` for Vercel Blob provisioning, environment variables, cron behavior,
endpoints, and release verification.
