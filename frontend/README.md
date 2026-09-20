# ArXiv Sentinel web application

The deployed Next.js application is both the dashboard and the production agent runtime. It:

- collects recent papers from arXiv, Semantic Scholar, and OpenAlex;
- ranks them with Gemini embeddings (with a deterministic lexical fallback);
- reconciles duplicate records across sources and scores novelty against prior runs;
- creates citation-validated summaries and corpus answers;
- persists daily digests and the rolling corpus in Vercel Blob; and
- runs ingestion every day at 06:30 UTC through Vercel Cron.

The production UI never reads committed sample data. Until the Blob store is connected and the
first ingestion completes, it shows an explicit setup/empty state.

## Local development

```bash
npm install
cp .env.example .env.local
npm run dev
```

For a full local run, provide `GEMINI_API_KEY`, `BLOB_READ_WRITE_TOKEN`, and `CRON_SECRET` in
`.env.local`. Scholar API keys are not required. OpenAlex recommends setting `OPENALEX_MAILTO`.
Never use a `NEXT_PUBLIC_` prefix for these values.

The protected ingestion route can then be invoked with:

```bash
curl -H "Authorization: Bearer $CRON_SECRET" http://localhost:3000/api/cron/ingest
```

## Production setup

The Vercel project uses `frontend` as its root directory.

1. Create and connect a **public Vercel Blob** store. Vercel injects the Blob credentials.
2. Add sensitive `GEMINI_API_KEY` and `CRON_SECRET` variables for Production and Preview.
3. Optionally set `OPENALEX_MAILTO`; tune limits using `.env.example`.
4. Deploy. `vercel.json` registers `GET /api/cron/ingest` for `30 6 * * *`.
5. Run the cron once after first deployment so the dashboard does not wait until the next window.

Production objects are written to:

- `arxiv-sentinel/digests/YYYY-MM-DD.json`
- `arxiv-sentinel/digests/latest.json`
- `arxiv-sentinel/corpus/latest.json`

The API routes are `GET /api/digest`, `GET /api/paper/:canonicalId`, `POST /api/ask`, and the
protected `GET /api/cron/ingest`.

## Grounding guarantees

Gemini receives only retrieved paper metadata and abstracts. Structured generation must return
verbatim, contiguous abstract spans. The server verifies every span and claim, retries invalid
output across the configured capable model fallback chain, and constructs the displayed answer
only from validated claims. When model access, quota, or validation still fails, the API returns
an explicit limited-confidence extractive result instead of unsupported prose.

## Verification

```bash
npm test
npm run lint
npm run build
```
