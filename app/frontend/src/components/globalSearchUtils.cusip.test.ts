/**
 * Tests the score() helper against CUSIP / CIK shaped inputs. The actual
 * GlobalSearch wiring (Math.min between ticker/CUSIP and fund/CIK) is exercised
 * indirectly here — the helper is what determines whether a CUSIP paste lands
 * as an exact-match hit.
 */
import { describe, expect, it } from "vitest";

import { score } from "./globalSearchUtils";

describe("score() against CUSIP / CIK queries", () => {
  it("exact-matches a 9-char CUSIP", () => {
    expect(score("037833100", "037833100")).toBe(0);
  });

  it("prefix-matches partial CUSIP entries", () => {
    expect(score("03783", "037833100")).toBe(1);
  });

  it("substring-matches CUSIP fragments", () => {
    const result = score("833100", "037833100");
    expect(result).toBeGreaterThanOrEqual(2);
  });

  it("exact-matches a zero-padded 10-digit CIK", () => {
    expect(score("0001807559", "0001807559")).toBe(0);
  });

  it("prefix-matches a partial CIK", () => {
    expect(score("000180", "0001807559")).toBe(1);
  });

  it("does not match when CUSIP/CIK fragment is absent", () => {
    expect(score("ZZZ", "037833100")).toBe(-1);
  });
});
