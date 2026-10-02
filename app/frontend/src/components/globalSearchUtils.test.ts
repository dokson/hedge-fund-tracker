/**
 * Tests for the substring-scoring used by the global search dropdown.
 * Lower score = better match; -1 means no match. CUSIP and CIK pastes go
 * through the same helper, so they share the table.
 */
import { describe, expect, it } from "vitest";

import { score } from "./globalSearchUtils";

describe("score", () => {
  it.each([
    ["exact match", "AAPL", "AAPL", 0],
    ["exact 9-char CUSIP", "037833100", "037833100", 0],
    ["exact zero-padded CIK", "0001807559", "0001807559", 0],
    ["case-insensitive exact match", "aapl", "AAPL", 0],
    ["query with surrounding whitespace", "  AAPL  ", "AAPL", 0],
    ["prefix match", "APP", "Apple Inc", 1],
    ["case-insensitive prefix match", "Tech", "technology", 1],
    ["partial CUSIP prefix", "03783", "037833100", 1],
    ["partial CIK prefix", "000180", "0001807559", 1],
    ["mid-string match (2 + index)", "apple", "The Apple Co", 6],
    ["CUSIP fragment (2 + index)", "833100", "037833100", 5],
    ["no match", "XYZ", "Apple Inc", -1],
    ["absent CUSIP fragment", "ZZZ", "037833100", -1],
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

  it("ranks prefix matches above mid-string matches", () => {
    expect(score("App", "Apple Inc")).toBeLessThan(score("App", "Big Apple Holdings"));
  });

  it("ranks earlier substring positions higher", () => {
    expect(score("inc", "Incorporated Co")).toBeLessThan(score("inc", "Apple Incorporated"));
  });
});
