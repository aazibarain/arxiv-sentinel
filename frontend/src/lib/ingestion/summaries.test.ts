import { describe, expect, it } from "vitest";

import { paper } from "../test-fixtures";
import { applyExtractiveFallback, summarizePapers, validateGroundedClaim } from "./summaries";

describe("grounded summaries", () => {
  it("accepts a claim with an exact supporting abstract span", () => {
    const source = paper();
    expect(() => validateGroundedClaim({
      claim: "The evaluated attack succeeds in 42 percent of tested tasks.",
      source_span: "The attack succeeds in 42 percent of the tested tasks",
    }, source)).not.toThrow();
  });

  it("rejects fabricated source spans", () => {
    expect(() => validateGroundedClaim({
      claim: "The method eliminates every successful attack in the evaluation.",
      source_span: "The method eliminated all attacks in every framework",
    }, paper())).toThrow(/not an exact abstract excerpt/);
  });

  it("produces an explicit limited-confidence extractive fallback", () => {
    const result = applyExtractiveFallback(paper(), "model quota exceeded");
    expect(result.summary_confidence).toBe("limited");
    expect(result.uncertainty).toContain("model quota exceeded");
    expect(result.summary_citations.length).toBeGreaterThan(0);
  });

  it("does not permanently reuse a limited-confidence fallback", async () => {
    const prior = paper({
      summary: "STALE FALLBACK",
      summary_confidence: "limited",
      summary_citations: [{ claim: "old", source_span: "old" }],
    });
    const current = paper({ summary: null, summary_confidence: null, summary_citations: [] });
    const apiKey = process.env.GEMINI_API_KEY;
    delete process.env.GEMINI_API_KEY;
    try {
      await summarizePapers([current], new Map([[prior.canonical_id, prior]]));
    } finally {
      if (apiKey) process.env.GEMINI_API_KEY = apiKey;
    }
    expect(current.summary).not.toBe("STALE FALLBACK");
    expect(current.uncertainty).toContain("GEMINI_API_KEY is not configured");
  });
});
