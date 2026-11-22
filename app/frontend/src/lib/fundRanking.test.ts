import { describe, expect, it } from "vitest";

import type { QuarterlyHolding, RawFundPerformanceRow } from "./data/types";
import { portfolioStats, rankFunds } from "./fundRanking";

const QUARTERS = ["2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2"];

/** One row per quarter for the fund's last `returns.length` quarters of the window. */
function rows(fund: string, returns: number[]): RawFundPerformanceRow[] {
  return QUARTERS.slice(QUARTERS.length - returns.length).map((quarter, i) => ({
    fund,
    quarter,
    fund_return: String(returns[i]),
    benchmark_return: "0.02",
    fund_cum_return: "",
    benchmark_cum_return: "",
    unpriced_weight: "0",
  }));
}

describe("rankFunds", () => {
  const ranking = rankFunds([
    ...rows("Long", Array(6).fill(0.1)),
    ...rows("Young", Array(4).fill(0.12)),
    ...rows("Tiny", [0.5, 0.5]),
    ...rows("Dip", [-0.2, 0.1, 0.3, 0.05]),
  ]);
  const byName = new Map(ranking.funds.map((f) => [f.fund, f]));

  it("ranks on %/yr, so a shorter record with the better pace leads a longer, bigger one", () => {
    expect(ranking.funds.map((f) => f.fund).slice(0, 2)).toEqual(["Young", "Long"]);
    expect(ranking.funds.at(-1)?.fund).toBe("Tiny");
  });

  it("annualises over the fund's own quarters and not below a year of them", () => {
    expect(byName.get("Long")?.annualReturn).toBeCloseTo(1.1 ** 4 - 1, 10);
    expect(byName.get("Young")?.annualReturn).toBeCloseTo(1.12 ** 4 - 1, 10);
    expect(byName.get("Tiny")?.annualReturn).toBeNull();
    expect(byName.get("Tiny")?.volatility).toBeNull();
  });

  it("measures the drawdown from the starting book, so a first-quarter loss counts", () => {
    expect(byName.get("Dip")?.maxDrawdown).toBeCloseTo(-0.2, 10);
    expect(byName.get("Long")?.maxDrawdown).toBe(0);
  });

  it("leaves the last-quarter return empty for a fund that did not report that quarter", () => {
    const withGap = rankFunds([
      ...rows("Full", [0.1, 0.1]),
      ...rows("Gap", [0.1, 0.1]).slice(0, 1),
    ]);
    const gap = withGap.funds.find((f) => f.fund === "Gap");
    expect(withGap.funds.find((f) => f.fund === "Full")?.lastReturn).toBeCloseTo(0.1, 10);
    expect(gap?.lastReturn).toBeNull();
  });
});

function holding(
  ticker: string,
  value: string,
  deltaValue: string,
  delta: string,
  cusip = ticker,
): QuarterlyHolding {
  return {
    cusip,
    ticker,
    company: ticker,
    shares: delta === "CLOSE" ? 0 : 1,
    deltaShares: 0,
    value,
    deltaValue,
    delta,
    portfolioPct: 0,
  };
}

describe("portfolioStats", () => {
  it("counts a sale into a closed position as turnover and a ticker's CUSIPs as one position", () => {
    const stats = portfolioStats([
      holding("AAA", "600", "600", "NEW"),
      holding("BBB", "300", "-100", "-25%"),
      holding("BBB", "100", "0", "NO CHANGE", "BBB-NOTE"),
      holding("CCC", "0", "-400", "CLOSE"),
      holding("Total", "1000", "100", "+11%"),
    ]);
    expect(stats.aum).toBe(1000);
    expect(stats.positions).toBe(2);
    // Bought 600, sold 100 + 400: the smaller side over the book.
    expect(stats.turnover).toBeCloseTo(0.5, 10);
    expect(stats.top10Weight).toBeCloseTo(1, 10);
  });
});
