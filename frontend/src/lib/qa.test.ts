import { describe, expect, it } from "vitest";

import { paper } from "./test-fixtures";
import { extractiveQAFallback, retrievePapers, validateQAOutput } from "./qa";

describe("corpus question answering", () => {
  it("retrieves papers using title and abstract evidence", () => {
    const relevant = paper();
    const unrelated = paper({
      canonical_id: "paper:weather",
      title: "Rainfall forecasting",
      abstract: "Historical station measurements improve regional precipitation forecasting over multiple seasons.",
    });
    expect(retrievePapers("How successful are prompt injection attacks?", [unrelated, relevant])[0]).toBe(relevant);
  });

  it("reconstructs an answer only from validated claims", () => {
    const result = validateQAOutput({
      answerability: "supported",
      uncertainty: "",
      citations: [{
        canonical_id: "paper:test",
        title: "ignored model title",
        claim: "The evaluated attack succeeds in 42 percent of tested tasks.",
        source_span: "The attack succeeds in 42 percent of the tested tasks",
      }],
    }, [paper()]);
    expect(result.answer).toContain("42 percent");
    expect(result.citations[0].title).toContain("Prompt injection");
  });

  it("rejects fabricated citation spans", () => {
    expect(() => validateQAOutput({
      answerability: "supported",
      uncertainty: "",
      citations: [{
        canonical_id: "paper:test",
        title: "",
        claim: "This fabricated claim is unsupported by any source in context.",
        source_span: "This text does not appear in the abstract at all",
      }],
    }, [paper()])).toThrow(/not a verbatim excerpt/);
  });

  it("labels fallback output as partial and preserves evidence", () => {
    const result = extractiveQAFallback("prompt injection attack", [paper()], "model unavailable");
    expect(result.answerability).toBe("partial");
    expect(result.citations.length).toBeGreaterThan(0);
    expect(result.uncertainty).toContain("model unavailable");
  });
});
