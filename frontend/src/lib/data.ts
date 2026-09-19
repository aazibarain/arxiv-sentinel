import rawDigest from "../../../backend/db/seed_digest.json";

import type { Digest, Paper } from "./types";

export const digest = rawDigest as unknown as Digest;

export function getPaper(canonicalId: string): Paper | undefined {
  return digest.papers.find((paper) => paper.canonical_id === canonicalId);
}

export function preferredSourceUrl(paper: Paper): string | null {
  for (const source of ["doi", "arxiv", "semantic_scholar", "openalex"]) {
    if (paper.source_urls[source]) return paper.source_urls[source];
  }
  return Object.values(paper.source_urls)[0] ?? null;
}

export function topicFor(paper: Paper): string {
  const text = `${paper.title} ${paper.abstract}`.toLowerCase();
  if (text.includes("jailbreak")) return "Jailbreaks";
  if (text.includes("backdoor") || text.includes("decept")) return "Model behavior";
  if (text.includes("prompt injection")) return "Prompt injection";
  return "AI security";
}
