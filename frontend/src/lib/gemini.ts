export function generationModels(): string[] {
  const primary = process.env.GEMINI_MODEL ?? "gemini-3.8-flash";
  const configuredFallbacks = process.env.GEMINI_FALLBACK_MODELS
    ?.split(",")
    .map((model) => model.trim())
    .filter(Boolean);
  return [...new Set([
    primary,
    ...(configuredFallbacks?.length
      ? configuredFallbacks
      : ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]),
  ])];
}

export function supportsThinkingLevel(model: string): boolean {
  return !model.includes("flash-lite");
}
