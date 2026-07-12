import { describe, expect, it } from "vitest";

import { enrichNQFiling, type FundQuarterSnapshot, type NonQuarterlyFiling } from "../dataService";

function mkFiling(overrides: Partial<NonQuarterlyFiling> = {}): NonQuarterlyFiling {
  return {
    fund: "Fund A",
    cusip: "000000000",
    ticker: "AAA",
    company: "A Corp",
    shares: 2000,
    value: "40K",
    avgPrice: "20",
    date: "2026-06-12",
    filingDate: "2026-06-16",
    ...overrides,
  };
}

function mkSnapshot(overrides: Partial<FundQuarterSnapshot> = {}): FundQuarterSnapshot {
  return {
    tickerMap: new Map([["AAA", { shares: 1000, portfolioPct: 4 }]]),
    totalValue: 1_000_000,
    ...overrides,
  };
}

describe("enrichNQFiling", () => {
  it("computes increase deltas against the fund's latest 13F position", () => {
    const e = enrichNQFiling(mkFiling(), mkSnapshot());

    expect(e.deltaType).toBe("INCREASE");
    expect(e.deltaShares).toBe(1000);
    expect(e.deltaPct).toBe(100);
    expect(e.quarterPortfolioPct).toBe(4);
  });

  it("estimates the portfolio percentage for NEW positions from the fund total", () => {
    const e = enrichNQFiling(
      mkFiling({ ticker: "BBB", value: "100K" }),
      mkSnapshot({ totalValue: 900_000 }),
    );

    expect(e.deltaType).toBe("NEW");
    expect(e.quarterPortfolioPct).toBeNull();
    // 100K over a merged total of 900K + 100K
    expect(e.estimatedPortfolioPct).toBeCloseTo(10);
  });

  it("leaves the estimate null when the fund total is unknown", () => {
    const e = enrichNQFiling(mkFiling({ ticker: "BBB" }), mkSnapshot({ totalValue: 0 }));

    expect(e.deltaType).toBe("NEW");
    expect(e.estimatedPortfolioPct).toBeNull();
  });

  it("marks zero-share filings as CLOSED", () => {
    const e = enrichNQFiling(mkFiling({ shares: 0, value: "0" }), mkSnapshot());

    expect(e.deltaType).toBe("CLOSED");
    expect(e.deltaShares).toBe(-1000);
  });

  it("handles funds with no quarter data at all", () => {
    const e = enrichNQFiling(mkFiling(), undefined);

    expect(e.deltaType).toBe("NEW");
    expect(e.quarterShares).toBe(0);
    expect(e.quarterPortfolioPct).toBeNull();
    expect(e.estimatedPortfolioPct).toBeNull();
  });
});
