import { describe, expect, it } from "vitest";

import {
  mergeNonQuarterlyHoldings,
  type EnrichedNQFiling,
  type FundTickerHolding,
} from "../dataService";

function mkHolding(overrides: Partial<FundTickerHolding> = {}): FundTickerHolding {
  return {
    fund: "Fund A",
    ticker: "AAA",
    company: "A Corp",
    shares: 1000,
    deltaShares: 0,
    value: 10_000,
    deltaValue: 0,
    portfolioPct: 5,
    portfolioPctRank: 1,
    sharesDeltaPct: 0,
    fundConcentrationRatio: 0,
    delta: "NO CHANGE",
    isBuyer: false,
    isSeller: false,
    isHolder: true,
    isNew: false,
    isClosed: false,
    isHighConviction: false,
    ...overrides,
  };
}

function mkFiling(overrides: Partial<EnrichedNQFiling> = {}): EnrichedNQFiling {
  return {
    fund: "Fund B",
    cusip: "000000000",
    ticker: "AAA",
    company: "A Corp",
    shares: 2000,
    value: "40K",
    avgPrice: "20",
    date: "2026-06-12",
    filingDate: "2026-06-16",
    quarterShares: null,
    deltaShares: null,
    deltaType: "NEW",
    deltaPct: null,
    quarterPortfolioPct: null,
    estimatedPortfolioPct: null,
    ...overrides,
  };
}

describe("mergeNonQuarterlyHoldings", () => {
  it("adds a NEW row for a fund with no 13F position", () => {
    const merged = mergeNonQuarterlyHoldings([mkHolding()], [mkFiling()]);

    expect(merged).toHaveLength(2);
    const added = merged.find((h) => h.fund === "Fund B");
    expect(added).toBeDefined();
    expect(added!.shares).toBe(2000);
    expect(added!.value).toBe(40_000);
    expect(added!.delta).toBe("NEW");
    expect(added!.isNew).toBe(true);
    expect(added!.isHolder).toBe(true);
    expect(added!.isBuyer).toBe(true);
  });

  it("updates an existing 13F row with the fresher share count", () => {
    const merged = mergeNonQuarterlyHoldings(
      [mkHolding({ fund: "Fund A", shares: 1000, value: 10_000 })],
      [mkFiling({ fund: "Fund A", shares: 1500, value: "15K" })],
    );

    expect(merged).toHaveLength(1);
    expect(merged[0].shares).toBe(1500);
    expect(merged[0].deltaShares).toBe(500);
    expect(merged[0].delta).toBe("+50.0%");
    expect(merged[0].isBuyer).toBe(true);
  });

  it("closes an existing 13F row on a zero-share filing", () => {
    const merged = mergeNonQuarterlyHoldings(
      [mkHolding({ fund: "Fund A", shares: 1000, value: 10_000 })],
      [mkFiling({ fund: "Fund A", shares: 0, value: "0" })],
    );

    expect(merged).toHaveLength(1);
    expect(merged[0].shares).toBe(0);
    expect(merged[0].delta).toBe("CLOSE");
    expect(merged[0].isClosed).toBe(true);
    expect(merged[0].isHolder).toBe(false);
    expect(merged[0].isSeller).toBe(true);
  });

  it("skips a zero-share filing for a fund that never held the stock", () => {
    const merged = mergeNonQuarterlyHoldings(
      [mkHolding()],
      [mkFiling({ fund: "Fund B", shares: 0, value: "0", deltaType: "CLOSED" })],
    );

    expect(merged).toHaveLength(1);
    expect(merged[0].fund).toBe("Fund A");
  });

  it("uses the filing's own delta when the fund has not filed this quarter yet", () => {
    // The fund's latest 13F is an older quarter: the enrichment already knows
    // the position increased vs that filing — it must NOT be labeled NEW.
    const merged = mergeNonQuarterlyHoldings(
      [],
      [
        mkFiling({
          fund: "Fund C",
          shares: 1500,
          value: "15K",
          quarterShares: 1000,
          deltaShares: 500,
          deltaType: "INCREASE",
          deltaPct: 50,
          quarterPortfolioPct: 67.1,
        }),
      ],
    );

    expect(merged).toHaveLength(1);
    expect(merged[0].delta).toBe("+50.0%");
    expect(merged[0].isNew).toBe(false);
    expect(merged[0].isBuyer).toBe(true);
    expect(merged[0].portfolioPct).toBeCloseTo(67.1);
    expect(merged[0].shares).toBe(1500);
    // Delta value approximated from the share delta's slice of the value.
    expect(merged[0].deltaValue).toBeCloseTo(5000);
  });

  it("shows a CLOSE row when a fund that held the stock in its last 13F sold out", () => {
    const merged = mergeNonQuarterlyHoldings(
      [],
      [
        mkFiling({
          fund: "Fund D",
          shares: 0,
          value: "0",
          quarterShares: 800,
          deltaShares: -800,
          deltaType: "CLOSED",
          quarterPortfolioPct: 3.2,
        }),
      ],
    );

    expect(merged).toHaveLength(1);
    expect(merged[0].delta).toBe("CLOSE");
    expect(merged[0].isClosed).toBe(true);
    expect(merged[0].shares).toBe(0);
    expect(merged[0].deltaShares).toBe(-800);
  });
});
