import { GoogleGenAI } from "@google/genai";

import { tokenJaccard, tokens } from "./text";
import type { Paper } from "../types";

const REFERENCE_TOPICS = [
  "Adversarial examples designed to evade image, audio, or text classifiers.",
  "Defenses and certified robustness guarantees against adversarial perturbations.",
  "Data poisoning and backdoor attacks against machine learning training pipelines.",
  "Model extraction, model stealing, and intellectual-property attacks on AI systems.",
  "Membership inference and training-data reconstruction attacks on learned models.",
  "Privacy leakage and unintended memorization in foundation models.",
  "Prompt injection attacks that manipulate large language model applications.",
  "Jailbreak attacks and alignment bypasses against large language models.",
  "Indirect prompt injection through tools, retrieval systems, or external content.",
  "Security of autonomous AI agents that call tools or act on external systems.",
  "Adversarial attacks on retrieval-augmented generation and vector databases.",
  "Supply-chain attacks involving machine learning models, datasets, or checkpoints.",
  "Detection and mitigation of malicious or deceptive model behavior.",
  "Red teaming, safety evaluation, and security benchmarks for generative AI.",
  "Robustness of multimodal and embodied AI systems under adversarial inputs.",
];

const HIGH_SIGNAL_PHRASES = [
  "adversarial attack",
  "adversarial example",
  "backdoor attack",
  "data poisoning",
  "jailbreak",
  "prompt injection",
  "model extraction",
  "model stealing",
  "membership inference",
  "privacy leakage",
  "training data reconstruction",
  "red teaming",
  "safety evaluation",
  "deceptive behavior",
  "certified robustness",
  "ai agent security",
  "security evaluation",
  "security benchmark",
  "safety evaluation",
  "privacy-preserving",
  "differential privacy",
];

const SECURITY_TERMS = [
  "attack", "adversarial", "backdoor", "defense", "exploit", "harm", "jailbreak",
  "malicious", "poisoning", "privacy", "robustness", "safety", "secure", "security",
  "spoofing", "stealing", "threat", "vulnerability",
];

const AI_TERMS = [
  "artificial intelligence", "machine learning", "language model", "neural", "llm", "agent",
  "classifier", "embedding", "transformer", "cnn", "model",
];

function cosine(left: number[], right: number[]): number {
  let dot = 0;
  let leftNorm = 0;
  let rightNorm = 0;
  for (let index = 0; index < Math.min(left.length, right.length); index += 1) {
    dot += left[index] * right[index];
    leftNorm += left[index] ** 2;
    rightNorm += right[index] ** 2;
  }
  return leftNorm && rightNorm ? dot / Math.sqrt(leftNorm * rightNorm) : 0;
}

async function embedTexts(texts: string[]): Promise<number[][]> {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) throw new Error("GEMINI_API_KEY is required for semantic relevance scoring.");
  const ai = new GoogleGenAI({ apiKey });
  const embeddings: number[][] = [];
  for (let index = 0; index < texts.length; index += 48) {
    const response = await ai.models.embedContent({
      model: process.env.GEMINI_EMBEDDING_MODEL ?? "gemini-embedding-001",
      contents: texts.slice(index, index + 48),
      config: { taskType: "SEMANTIC_SIMILARITY", outputDimensionality: 256 },
    });
    const values = (response.embeddings ?? []).map((embedding) => embedding.values ?? []);
    if (values.length !== Math.min(48, texts.length - index) || values.some((value) => !value.length)) {
      throw new Error("Gemini returned an incomplete embedding batch.");
    }
    embeddings.push(...values);
  }
  return embeddings;
}

export function lexicalRelevance(paper: Paper): number {
  const title = paper.title.toLowerCase();
  const body = `${paper.title} ${paper.abstract}`.toLowerCase();
  const maxReference = Math.max(...REFERENCE_TOPICS.map((reference) => tokenJaccard(body, reference)));
  const titleHits = HIGH_SIGNAL_PHRASES.filter((phrase) => title.includes(phrase)).length;
  const bodyHits = HIGH_SIGNAL_PHRASES.filter((phrase) => body.includes(phrase)).length;
  const securityTokens = ["attack", "defense", "security", "privacy", "robustness", "unsafe", "exploit"];
  const documentTokens = tokens(body);
  const securityCoverage = securityTokens.filter((token) => documentTokens.has(token)).length / securityTokens.length;
  return Math.min(1, maxReference * 3.4 + titleHits * 0.16 + bodyHits * 0.055 + securityCoverage * 0.18);
}

export function hasSecurityIntent(paper: Paper): boolean {
  const body = ` ${paper.title} ${paper.abstract} `.toLowerCase();
  if (HIGH_SIGNAL_PHRASES.some((phrase) => body.includes(phrase))) return true;
  return SECURITY_TERMS.some((term) => body.includes(term)) &&
    AI_TERMS.some((term) => body.includes(term));
}

export async function filterAndRank(papers: Paper[]): Promise<{
  papers: Paper[];
  method: "gemini_embedding" | "lexical_fallback";
  warning?: string;
}> {
  if (!papers.length) return { papers: [], method: "lexical_fallback" };
  const threshold = Number(process.env.RELEVANCE_THRESHOLD ?? "0.48");
  try {
    const texts = [...REFERENCE_TOPICS, ...papers.map((paper) => `${paper.title}\n${paper.abstract}`)];
    const embeddings = await embedTexts(texts);
    const references = embeddings.slice(0, REFERENCE_TOPICS.length);
    papers.forEach((paper, index) => {
      const semanticScore = Math.max(
        ...references.map((reference) => cosine(embeddings[REFERENCE_TOPICS.length + index], reference)),
      );
      paper.relevance_score = semanticScore * 0.75 + lexicalRelevance(paper) * 0.25;
    });
    return {
      papers: papers
        .filter((paper) => hasSecurityIntent(paper) && (paper.relevance_score ?? -1) >= threshold)
        .sort((left, right) => (right.relevance_score ?? 0) - (left.relevance_score ?? 0)),
      method: "gemini_embedding",
    };
  } catch (error) {
    const warning = error instanceof Error ? error.message : "Semantic relevance scoring failed";
    console.warn("[ingest:relevance] using lexical fallback", warning);
    papers.forEach((paper) => {
      paper.relevance_score = lexicalRelevance(paper);
    });
    const fallbackThreshold = Number(process.env.LEXICAL_RELEVANCE_THRESHOLD ?? "0.34");
    return {
      papers: papers
        .filter((paper) => hasSecurityIntent(paper) && (paper.relevance_score ?? 0) >= fallbackThreshold)
        .sort((left, right) => (right.relevance_score ?? 0) - (left.relevance_score ?? 0)),
      method: "lexical_fallback",
      warning,
    };
  }
}

export function annotateNovelty(papers: Paper[], priorCorpus: Paper[]): Paper[] {
  for (const paper of papers) {
    let highestSimilarity = 0;
    for (const prior of priorCorpus) {
      const similarity = prior.canonical_id === paper.canonical_id
        ? 1
        : tokenJaccard(`${paper.title} ${paper.abstract}`, `${prior.title} ${prior.abstract}`);
      highestSimilarity = Math.max(highestSimilarity, similarity);
    }
    paper.novelty_score = Math.max(0, 1 - highestSimilarity);
    paper.novelty_verdict = highestSimilarity >= 0.92
      ? "duplicate"
      : highestSimilarity >= 0.75
        ? "incremental"
        : "novel";
  }
  return papers;
}
