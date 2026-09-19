import "server-only";

import { get, put } from "@vercel/blob";

import type { CorpusSnapshot, Digest, DigestLoadResult, Paper } from "./types";

const LATEST_DIGEST_PATH = "arxiv-sentinel/digests/latest.json";
const CORPUS_PATH = "arxiv-sentinel/corpus/latest.json";

export function isStorageConfigured(): boolean {
  return Boolean(process.env.BLOB_READ_WRITE_TOKEN || process.env.BLOB_STORE_ID);
}

async function readJsonBlob<T>(pathname: string): Promise<T | null> {
  if (!isStorageConfigured()) return null;
  const blob = await get(pathname, { access: "public" });
  if (!blob || blob.statusCode !== 200 || !blob.stream) return null;
  return JSON.parse(await new Response(blob.stream).text()) as T;
}

async function writeJsonBlob(pathname: string, value: unknown): Promise<void> {
  if (!isStorageConfigured()) {
    throw new Error("Vercel Blob is not configured for this deployment.");
  }
  await put(pathname, JSON.stringify(value), {
    access: "public",
    addRandomSuffix: false,
    allowOverwrite: true,
    cacheControlMaxAge: 60,
    contentType: "application/json",
  });
}

export async function loadLatestDigest(): Promise<DigestLoadResult> {
  if (!isStorageConfigured()) {
    return {
      digest: null,
      state: "unconfigured",
      detail: "Durable digest storage has not been connected yet.",
    };
  }
  try {
    const digest = await readJsonBlob<Digest>(LATEST_DIGEST_PATH);
    return digest
      ? { digest, state: digest.papers.length ? "ready" : "empty" }
      : {
          digest: null,
          state: "empty",
          detail: "The first scheduled ingestion has not completed yet.",
        };
  } catch (error) {
    console.error("[digest:read] failed", error);
    return {
      digest: null,
      state: "error",
      detail: "The live digest store could not be reached.",
    };
  }
}

export async function loadCorpus(): Promise<CorpusSnapshot> {
  const corpus = await readJsonBlob<CorpusSnapshot>(CORPUS_PATH);
  return corpus ?? { generated_at: new Date(0).toISOString(), papers: [] };
}

export async function getPaper(canonicalId: string): Promise<Paper | undefined> {
  const corpus = await loadCorpus();
  return corpus.papers.find((paper) => paper.canonical_id === canonicalId);
}

export async function saveDigest(digest: Digest, corpus: CorpusSnapshot): Promise<void> {
  await Promise.all([
    writeJsonBlob(`arxiv-sentinel/digests/${digest.digest_date}.json`, digest),
    writeJsonBlob(LATEST_DIGEST_PATH, digest),
    writeJsonBlob(CORPUS_PATH, corpus),
  ]);
}
