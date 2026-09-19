# ArXiv Sentinel

ArXiv Sentinel is an autonomous research-monitoring agent for adversarial machine
learning and AI security. It discovers newly published work from arXiv, Semantic
Scholar, and OpenAlex, normalizes every result into one schema, and makes the final
relevance decision with semantic embeddings rather than keyword rules.

This repository currently contains the Phase 1 through Phase 3 vertical slices:

- adapters for all three research sources;
- a shared, validated `PaperRecord` contract;
- local sentence-transformer embeddings and reference-set relevance scoring;
- a fault-isolated async pipeline and runnable CLI;
- persistent Chroma memory with cosine nearest-neighbor retrieval;
- explainable novelty verdicts with links to the closest prior papers;
- keyless Semantic Scholar and OpenAlex research tools;
- structured Gemini summaries with claim-to-abstract citations;
- a programmatic grounding gate that rejects and retries unsupported output;
- deterministic tests for ingestion, relevance, novelty, tools, and grounding.

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
  keyless citation and metadata enrichment
                  |
                  v
      Gemini structured summary generation
                  |
                  v
 programmatic claim/span grounding validation
                  |
                  v
          enriched JSON / terminal digest
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

## Roadmap

- Phase 4: cross-source identity reconciliation.
- Phase 5: FastAPI digest/Q&A endpoints and the Next.js dashboard.
- Phase 6: scheduled ingestion after persistence/deployment decisions are settled.
