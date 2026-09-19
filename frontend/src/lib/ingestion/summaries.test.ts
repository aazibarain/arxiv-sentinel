import { describe, expect, it } from "vitest";

import { paper } from "../test-fixtures";
import { applyExtractiveFallback, validateGroundedClaim } from "./summaries";

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
});
