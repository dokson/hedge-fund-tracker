/**
 * Tests for the substring-scoring used by the global search dropdown.
 * Lower score = better match; -1 means no match.
 */
import { describe, expect, it } from "vitest";

import { score } from "./globalSearchUtils";

describe("score", () => {
  it.each([
    ["exact match", "AAPL", "AAPL", 0],
    ["case-insensitive exact match", "aapl", "AAPL", 0],
    ["query with surrounding whitespace", "  AAPL  ", "AAPL", 0],
    ["prefix match", "APP", "Apple Inc", 1],
    ["mid-string match (2 + index)", "apple", "The Apple Co", 6],
    ["no match", "XYZ", "Apple Inc", -1],
  ])("%s", (_case, query, target, expected) => {
    expect(score(query, target)).toBe(expected);
  });

  it("returns -1 for an empty query so blank input never lists every row", () => {
    expect(score("", "Apple Inc")).toBe(-1);
    expect(score("   ", "Apple Inc")).toBe(-1);
  });

  it("returns -1 when the target is null, undefined or empty (no crash)", () => {
    expect(score("AAPL", null)).toBe(-1);
    expect(score("AAPL", undefined)).toBe(-1);
    expect(score("AAPL", "")).toBe(-1);
  });
});
