import { normalizeText, tokenCoverage, tokens } from "./ingestion/text";
import { preferredSourceUrl } from "./papers";
import type { AnswerCitation, Paper, QAAnswer } from "./types";

export type QAModelOutput = {
  answerability: "supported" | "partial" | "insufficient";
  uncertainty: string;
  citations: Array<Omit<AnswerCitation, "source_url">>;
};

export function retrievePapers(question: string, corpus: Paper[], limit = 6): Paper[] {
  const queryTokens = tokens(question);
  if (!queryTokens.size) return [];
  const documentFrequency = new Map<string, number>();
  for (const token of queryTokens) {
    documentFrequency.set(
      token,
      corpus.filter((paper) => tokens(`${paper.title} ${paper.abstract}`).has(token)).length,
    );
  }
  return corpus
    .map((paper) => {
      const titleTokens = tokens(paper.title);
      const documentTokens = tokens(`${paper.title} ${paper.abstract}`);
      let score = 0;
      for (const token of queryTokens) {
        if (!documentTokens.has(token)) continue;
        const idf = Math.log((corpus.length + 1) / ((documentFrequency.get(token) ?? 0) + 1)) + 1;
        score += idf * (titleTokens.has(token) ? 2.2 : 1);
      }
      return { paper, score: score / Math.max(1, queryTokens.size) };
    })
    .filter(({ score }) => score > 0)
    .sort((left, right) => right.score - left.score || (right.paper.relevance_score ?? 0) - (left.paper.relevance_score ?? 0))
    .slice(0, limit)
    .map(({ paper }) => paper);
}

function withPeriod(value: string): string {
  const trimmed = value.trim();
  return /[.!?]$/.test(trimmed) ? trimmed : `${trimmed}.`;
}

export function validateQAOutput(output: QAModelOutput, papers: Paper[]): QAAnswer {
  if (output.answerability === "insufficient") {
    if (output.citations.length) throw new Error("An insufficient answer must not invent citations.");
    return {
      answer: "The monitored corpus does not contain enough direct evidence to answer that question reliably.",
      citations: [],
      retrieved_paper_ids: papers.map((paper) => paper.canonical_id),
      answerability: "insufficient",
      uncertainty: output.uncertainty.trim() || "No sufficiently relevant abstract evidence was found.",
    };
  }
  if (!output.citations.length) throw new Error("A supported answer requires at least one citation.");
  if (output.answerability === "partial" && !output.uncertainty.trim()) {
    throw new Error("A partial answer must state what the corpus cannot establish.");
  }
  const byId = new Map(papers.map((paper) => [paper.canonical_id, paper]));
  const citations = output.citations.map((citation) => {
    const paper = byId.get(citation.canonical_id);
    if (!paper) throw new Error("The answer cited a paper outside the retrieval context.");
    const normalizedSpan = normalizeText(citation.source_span);
    if (normalizedSpan.split(" ").length < 5 || !normalizeText(paper.abstract).includes(normalizedSpan)) {
      throw new Error("A citation span was not a verbatim excerpt from its source abstract.");
    }
    if (citation.claim.trim().split(/\s+/).length < 8 || tokenCoverage(citation.claim, citation.source_span) < 0.34) {
      throw new Error("A citation claim was vague or not supported by its evidence span.");
    }
    return {
      ...citation,
      title: paper.title,
      source_url: preferredSourceUrl(paper),
    };
  });
  return {
    answer: citations.map((citation) => withPeriod(citation.claim)).join(" "),
    citations,
    retrieved_paper_ids: papers.map((paper) => paper.canonical_id),
    answerability: output.answerability,
    uncertainty: output.uncertainty.trim() || null,
  };
}

function sentences(value: string): string[] {
  return value
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence.split(/\s+/).length >= 8);
}

export function extractiveQAFallback(question: string, papers: Paper[], reason: string): QAAnswer {
  const queryTokens = tokens(question);
  const candidates = papers
    .flatMap((paper) => sentences(paper.abstract).map((sentence) => ({ paper, sentence })))
    .map((candidate) => ({
      ...candidate,
      score: [...queryTokens].filter((token) => tokens(candidate.sentence).has(token)).length,
    }))
    .filter((candidate) => candidate.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, 3);
  if (!candidates.length) {
    return {
      answer: "The monitored corpus does not contain enough direct evidence to answer that question reliably.",
      citations: [],
      retrieved_paper_ids: papers.map((paper) => paper.canonical_id),
      answerability: "insufficient",
      uncertainty: `Grounded generation was unavailable and no matching extract could be found: ${reason}`,
    };
  }
  const citations = candidates.map(({ paper, sentence }) => ({
    canonical_id: paper.canonical_id,
    title: paper.title,
    claim: sentence,
    source_span: sentence,
    source_url: preferredSourceUrl(paper),
  }));
  return {
    answer: citations.map((citation) => citation.claim).join(" "),
    citations,
    retrieved_paper_ids: papers.map((paper) => paper.canonical_id),
    answerability: "partial",
    uncertainty: `This is an extractive fallback. The corpus may not fully answer the question: ${reason}`,
  };
}
