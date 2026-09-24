import { describe, expect, it } from "vitest";

import { isModelProvider } from "../data/models";

describe("isModelProvider", () => {
  it("accepts every known provider", () => {
    for (const p of ["Groq", "Google", "HuggingFace", "OpenRouter"]) {
      expect(isModelProvider(p)).toBe(true);
    }
  });

  it("rejects unknown or differently-cased values", () => {
    expect(isModelProvider("groq")).toBe(false);
    expect(isModelProvider("")).toBe(false);
    expect(isModelProvider("Anthropic")).toBe(false);
  });
});
