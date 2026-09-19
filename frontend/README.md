# ArXiv Sentinel dashboard

Next.js 16 dashboard for the ArXiv Sentinel research-monitoring agent. It provides:

- the filterable daily AI-security digest;
- paper detail views with exact abstract evidence;
- server-side, citation-validated Gemini corpus Q&A;
- deployable API routes for the committed demonstration digest.

## Local development

```bash
npm install
cp .env.example .env.local
npm run dev
```

Set `GEMINI_API_KEY` in `.env.local` to enable `/api/ask`. The key is read only by
the server route and is never exposed through a `NEXT_PUBLIC_` variable.

## Verification

```bash
npm run lint
npm run build
```

## Vercel

The Vercel project is connected to the repository with `frontend` as its root
directory. Pushes to `main` create production deployments; other branches create
previews. Configure `GEMINI_API_KEY` as a sensitive Vercel environment variable in
both Production and Preview to enable grounded Q&A in those environments.
