export type NoveltyVerdict = "novel" | "incremental" | "duplicate";

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
  summary_citations: SummaryCitation[];
  ingested_at: string;
}

export interface Digest {
  digest_date: string;
  papers: Paper[];
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
}
