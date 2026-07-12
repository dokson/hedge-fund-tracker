import { describe, expect, it } from "vitest";

import { smartScoreCore } from "../smartScore";
import { selectSmartScoreScreen } from "../strategyScreen";
import type { StockQuarterAnalysis } from "../dataService";

function mkRow(overrides: Partial<StockQuarterAnalysis>): StockQuarterAnalysis {
  return {
    ticker: "AAA",
    company: "A Corp",
    totalValue: 0,
    totalDeltaValue: 0,
    maxPortfolioPct: 0,
    avgPortfolioPct: 0,
    buyerCount: 0,
    sellerCount: 0,
    holderCount: 0,
    newHolderCount: 0,
    closeCount: 0,
    highConvictionCount: 0,
    netBuyers: 0,
    buyerSellerRatio: 0,
    ownershipDeltaAvg: 0,
    fundConcentrationAvg: 0,
    delta: 0,
    ...overrides,
  };
}

const rows = [
  mkRow({
    ticker: "AAA",
    holderCount: 10,
    netBuyers: 8,
    avgPortfolioPct: 5,
    highConvictionCount: 2,
  }),
  mkRow({
    ticker: "BBB",
    holderCount: 5,
    netBuyers: 0,
    avgPortfolioPct: 2,
    highConvictionCount: 1,
  }),
  mkRow({
    ticker: "CCC",
    holderCount: 1,
    netBuyers: -4,
    avgPortfolioPct: 0.5,
    highConvictionCount: 0,
  }),
];

describe("smartScoreCore", () => {
  it("mirrors the Python percentile core (average ties, HC absent when zero)", () => {
    const scores = smartScoreCore(rows);

    // Hand-computed against pandas rank(pct=True) with the conviction bonus:
    // AAA (100, 100, min(100, 100+20)) → 10; BBB (66.7, 66.7, 76.7) → 7.3;
    // CCC (33.3, 33.3, 33.3) → 4.0.
    expect(scores[0]).toBeCloseTo(10.0, 1);
    expect(scores[1]).toBeCloseTo(7.3, 1);
    expect(scores[2]).toBeCloseTo(4.0, 1);
  });
});

describe("selectSmartScoreScreen", () => {
  it("ranks by the core descending, caps at topN and normalizes weights", () => {
    const screen = selectSmartScoreScreen(rows, 2);

    expect(screen.map((h) => h.ticker)).toEqual(["AAA", "BBB"]);
    expect(screen.reduce((s, h) => s + h.weight, 0)).toBeCloseTo(1.0);
  });
});
