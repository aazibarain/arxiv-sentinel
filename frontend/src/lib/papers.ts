import type { Paper } from "./types";

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
  if (text.includes("privacy") || text.includes("membership inference")) return "Privacy";
  if (text.includes("adversarial") || text.includes("robustness")) return "Adversarial ML";
  return "AI security";
}
