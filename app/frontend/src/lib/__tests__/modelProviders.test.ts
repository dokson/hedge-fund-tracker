import { describe, expect, it } from "vitest";

import { isModelProvider } from "../data/models";

describe("isModelProvider", () => {
  it("rejects unknown or differently-cased values", () => {
    expect(isModelProvider("groq")).toBe(false);
    expect(isModelProvider("")).toBe(false);
    expect(isModelProvider("Anthropic")).toBe(false);
  });
});
