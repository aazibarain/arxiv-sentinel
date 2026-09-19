import type { Paper } from "./types";

export function paper(overrides: Partial<Paper> = {}): Paper {
  return {
    canonical_id: "paper:test",
    title: "Prompt injection attacks against tool-using language model agents",
    abstract:
      "We evaluate indirect prompt injection attacks against language model agents that use external tools. The attack succeeds in 42 percent of the tested tasks, while instruction isolation reduces successful attacks to 11 percent. Our results are limited to two agent frameworks and do not establish robustness in other deployment settings.",
    authors: ["Ada Researcher", "Sam Scientist"],
    published_date: "2026-09-18",
    source_ids: { arxiv: "2609.12345" },
    source_urls: { arxiv: "https://arxiv.org/abs/2609.12345" },
    citation_count: 2,
    relevance_score: 0.9,
    novelty_score: 1,
    novelty_verdict: "novel",
    summary: null,
    why_it_matters: null,
    summary_confidence: null,
    uncertainty: null,
    summary_citations: [],
    ingested_at: "2026-09-19T00:00:00.000Z",
    ...overrides,
  };
}
