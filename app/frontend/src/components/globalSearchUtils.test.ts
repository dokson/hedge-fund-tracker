/**
 * Tests for the substring-scoring used by the global search dropdown.
 * Lower score = better match; -1 means no match.
 */
import { describe, expect, it } from "vitest";

import { score } from "./globalSearchUtils";

describe("score", () => {
  it("returns 0 for an exact match", () => {
    expect(score("AAPL", "AAPL")).toBe(0);
  });

  it("returns 1 for a prefix match", () => {
    expect(score("APP", "Apple Inc")).toBe(1);
  });

  it("returns 2 plus the position for a substring match in the middle", () => {
    expect(score("apple", "The Apple Co")).toBe(6); // 2 + index 4 of "apple"
  });

  it("is case-insensitive", () => {
    expect(score("aapl", "AAPL")).toBe(0);
    expect(score("Tech", "technology")).toBe(1);
  });

  it("trims surrounding whitespace from the query", () => {
    expect(score("  AAPL  ", "AAPL")).toBe(0);
  });

  it("returns -1 when there is no match", () => {
    expect(score("XYZ", "Apple Inc")).toBe(-1);
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

  it("ranks prefix matches above mid-string matches", () => {
    const prefix = score("App", "Apple Inc");
    const middle = score("App", "Big Apple Holdings");
    expect(prefix).toBeLessThan(middle);
  });

  it("ranks earlier substring positions higher", () => {
    const early = score("inc", "Incorporated Co");
    const late = score("inc", "Apple Incorporated");
    expect(early).toBeLessThan(late);
  });
});
