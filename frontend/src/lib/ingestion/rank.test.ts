import { describe, expect, it } from "vitest";

import { paper } from "../test-fixtures";
import { annotateNovelty, hasSecurityIntent, lexicalRelevance } from "./rank";

describe("ranking fallbacks", () => {
  it("gives security research a higher lexical score than unrelated work", () => {
    const relevant = lexicalRelevance(paper());
    const unrelated = lexicalRelevance(paper({
      title: "Seasonal rainfall prediction",
      abstract: "We study precipitation patterns using historical weather station observations across multiple regions.",
    }));
    expect(relevant).toBeGreaterThan(unrelated);
    expect(relevant).toBeGreaterThan(0.34);
  });

  it("marks an identical known paper as a duplicate", () => {
    const current = paper({ novelty_score: null, novelty_verdict: null });
    annotateNovelty([current], [paper()]);
    expect(current.novelty_score).toBe(0);
    expect(current.novelty_verdict).toBe("duplicate");
  });

  it("requires both an AI context and a security intent", () => {
    expect(hasSecurityIntent(paper())).toBe(true);
    expect(hasSecurityIntent(paper({
      title: "Artificial intelligence in Maritime English education",
      abstract: "This paper studies the use of AI tools for language instruction and digital teaching resources.",
    }))).toBe(false);
    expect(hasSecurityIntent(paper({
      title: "Network security policy review",
      abstract: "This review covers credential policy, firewall rules, and conventional database administration.",
    }))).toBe(false);
  });
});
