export type NoveltyVerdict = "novel" | "incremental" | "duplicate";
export type SummaryConfidence = "high" | "moderate" | "limited";

export interface SummaryCitation {
  claim: string;
  source_span: string;
}

export interface Paper {
  canonical_id: string;
  title: string;
  abstract: string;
  authors: string[];
  published_date: string;
  source_ids: Record<string, string>;
  source_urls: Record<string, string>;
  citation_count: number | null;
  relevance_score: number | null;
  novelty_score: number | null;
  novelty_verdict: NoveltyVerdict | null;
  summary: string | null;
  why_it_matters: string | null;
  summary_confidence?: SummaryConfidence | null;
  uncertainty?: string | null;
  summary_citations: SummaryCitation[];
  ingested_at: string;
}

export interface Digest {
  digest_date: string;
  generated_at: string;
  candidate_count: number;
  relevant_count: number;
  deduplicated_count: number;
  source_counts: Record<string, number>;
  source_errors: Record<string, string>;
  pipeline_warnings: string[];
  relevance_method: "gemini_embedding" | "lexical_fallback";
  papers: Paper[];
}

export interface CorpusSnapshot {
  generated_at: string;
  papers: Paper[];
}

export interface DigestLoadResult {
  digest: Digest | null;
  state: "ready" | "empty" | "unconfigured" | "error";
  detail?: string;
}

export interface AnswerCitation {
  canonical_id: string;
  title: string;
  claim: string;
  source_span: string;
  source_url: string | null;
}

export interface QAAnswer {
  answer: string;
  citations: AnswerCitation[];
  retrieved_paper_ids: string[];
  answerability: "supported" | "partial" | "insufficient";
  uncertainty: string | null;
}
