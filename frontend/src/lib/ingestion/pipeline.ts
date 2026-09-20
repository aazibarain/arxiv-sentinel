import { loadCorpus, saveDigest } from "../data";
import type { CorpusSnapshot, Digest, Paper } from "../types";
import { annotateNovelty, filterAndRank } from "./rank";
import { fetchAllSources } from "./sources";
import { summarizePapers } from "./summaries";
import { reconcilePapers } from "./text";

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function mergeCorpus(prior: Paper[], current: Paper[], generatedAt: string): CorpusSnapshot {
  const byId = new Map(prior.map((paper) => [paper.canonical_id, paper]));
  current.forEach((paper) => {
    const existing = byId.get(paper.canonical_id);
    byId.set(paper.canonical_id, {
      ...paper,
      ingested_at: existing?.ingested_at ?? paper.ingested_at,
    });
  });
  const maxCorpusPapers = Number(process.env.CORPUS_MAX_PAPERS ?? "1000");
  return {
    generated_at: generatedAt,
    papers: [...byId.values()]
      .sort((left, right) =>
        right.published_date.localeCompare(left.published_date) ||
        (right.relevance_score ?? 0) - (left.relevance_score ?? 0),
      )
      .slice(0, maxCorpusPapers),
  };
}

export async function runProductionIngestion(target = new Date()): Promise<Digest> {
  const targetDate = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth(), target.getUTCDate()));
  const endDate = new Date(targetDate);
  endDate.setUTCDate(endDate.getUTCDate() + 1);
  const startDate = new Date(targetDate);
  startDate.setUTCDate(startDate.getUTCDate() - Number(process.env.INGESTION_LOOKBACK_DAYS ?? "7"));
  const limitPerSource = Number(process.env.INGESTION_LIMIT_PER_SOURCE ?? "30");
  const maxDigestPapers = Number(process.env.DIGEST_MAX_PAPERS ?? "15");
  const generatedAt = new Date().toISOString();

  console.log("[ingest] starting", {
    targetDate: isoDate(targetDate),
    startDate: isoDate(startDate),
    endDate: isoDate(endDate),
    limitPerSource,
  });
  const [sourceResult, priorCorpus] = await Promise.all([
    fetchAllSources(isoDate(startDate), isoDate(endDate), limitPerSource),
    loadCorpus(),
  ]);
  if (!sourceResult.papers.length && Object.keys(sourceResult.sourceErrors).length === 3) {
    throw new Error("All research sources failed; the previous digest was left untouched.");
  }

  const ranking = await filterAndRank(sourceResult.papers);
  const allReconciled = reconcilePapers(ranking.papers);
  const priorToTarget = priorCorpus.papers.filter(
    (paper) => paper.ingested_at.slice(0, 10) < isoDate(targetDate),
  );
  annotateNovelty(allReconciled, priorToTarget);
  const verdictPriority = { novel: 0, incremental: 1, duplicate: 2 } as const;
  const reconciled = allReconciled
    .sort((left, right) =>
      verdictPriority[left.novelty_verdict ?? "novel"] - verdictPriority[right.novelty_verdict ?? "novel"] ||
      (right.relevance_score ?? 0) - (left.relevance_score ?? 0),
    )
    .slice(0, maxDigestPapers);
  await summarizePapers(reconciled, new Map(priorCorpus.papers.map((paper) => [paper.canonical_id, paper])));

  const digest: Digest = {
    digest_date: isoDate(targetDate),
    generated_at: generatedAt,
    candidate_count: sourceResult.papers.length,
    relevant_count: ranking.papers.length,
    deduplicated_count: ranking.papers.length - allReconciled.length,
    source_counts: sourceResult.sourceCounts,
    source_errors: sourceResult.sourceErrors,
    pipeline_warnings: ranking.warning ? [`Semantic ranking fallback: ${ranking.warning}`] : [],
    relevance_method: ranking.method,
    papers: reconciled,
  };
  const corpus = mergeCorpus(priorCorpus.papers, reconciled, generatedAt);
  await saveDigest(digest, corpus);
  console.log("[ingest] completed", {
    candidateCount: digest.candidate_count,
    relevantCount: digest.relevant_count,
    digestCount: digest.papers.length,
    sourceCounts: digest.source_counts,
    sourceErrors: digest.source_errors,
  });
  return digest;
}
