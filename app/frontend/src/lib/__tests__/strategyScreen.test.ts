import { describe, expect, it } from "vitest";

import { selectStrategyScreen } from "../strategyScreen";
import { STRATEGY_BY_TAB } from "../strategies";
import type { StockQuarterAnalysis } from "../dataService";

const stock = (over: Partial<StockQuarterAnalysis>): StockQuarterAnalysis => ({
  ticker: "X",
  company: "X Corp",
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
  ...over,
});

const ROWS = [
  stock({ ticker: "AAA", holderCount: 20, avgPortfolioPct: 10, netBuyers: 8 }),
  stock({ ticker: "BBB", holderCount: 16, avgPortfolioPct: 5, netBuyers: 12 }),
  stock({ ticker: "CCC", holderCount: 8, avgPortfolioPct: 8, netBuyers: 1 }),
];

describe("selectStrategyScreen", () => {
  it("avg_portfolio: filters by min holders and weights by avgPortfolioPct", () => {
    const holdings = selectStrategyScreen(ROWS, STRATEGY_BY_TAB.avgportfolio, 15);
    expect(holdings.map((h) => h.ticker)).toEqual(["AAA", "BBB"]); // CCC dropped (8 < 15)
    expect(holdings[0].weight).toBeCloseTo(10 / 15, 6);
    expect(holdings[1].weight).toBeCloseTo(5 / 15, 6);
  });

  it("consensus: ranks by netBuyers and caps at top-N, no min holders", () => {
    const holdings = selectStrategyScreen(ROWS, { ...STRATEGY_BY_TAB.consensus, topN: 2 }, 15);
    expect(holdings.map((h) => h.ticker)).toEqual(["BBB", "AAA"]); // 12, 8 (CCC=1 capped out)
  });

  it("flags new positions (infinite delta) and carries delta otherwise", () => {
    const rows = [
      stock({ ticker: "NEWP", holderCount: 20, avgPortfolioPct: 5, delta: Infinity }),
      stock({ ticker: "GROW", holderCount: 20, avgPortfolioPct: 5, delta: 30 }),
    ];
    const holdings = selectStrategyScreen(rows, STRATEGY_BY_TAB.avgportfolio, 15);
    const newp = holdings.find((h) => h.ticker === "NEWP")!;
    const grow = holdings.find((h) => h.ticker === "GROW")!;
    expect(newp.isNew).toBe(true);
    expect(newp.deltaPct).toBe(0);
    expect(grow.isNew).toBe(false);
    expect(grow.deltaPct).toBe(30);
  });
});
