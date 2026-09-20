import { afterEach, describe, expect, it } from "vitest";

import { generationModels } from "./gemini";

const originalPrimary = process.env.GEMINI_MODEL;
const originalFallbacks = process.env.GEMINI_FALLBACK_MODELS;

afterEach(() => {
  if (originalPrimary === undefined) delete process.env.GEMINI_MODEL;
  else process.env.GEMINI_MODEL = originalPrimary;
  if (originalFallbacks === undefined) delete process.env.GEMINI_FALLBACK_MODELS;
  else process.env.GEMINI_FALLBACK_MODELS = originalFallbacks;
});

describe("Gemini model routing", () => {
  it("uses capable default fallbacks without duplicating the primary", () => {
    process.env.GEMINI_MODEL = "gemini-3.8-flash";
    delete process.env.GEMINI_FALLBACK_MODELS;
    expect(generationModels()).toEqual([
      "gemini-3.8-flash",
      "gemini-3.7-flash",
      "gemini-3.6-flash",
    ]);
  });

  it("honors configured fallback order", () => {
    process.env.GEMINI_MODEL = "primary";
    process.env.GEMINI_FALLBACK_MODELS = "secondary, tertiary, secondary";
    expect(generationModels()).toEqual(["primary", "secondary", "tertiary"]);
  });
});
