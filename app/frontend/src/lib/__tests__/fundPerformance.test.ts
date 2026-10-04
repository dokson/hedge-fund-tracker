import { describe, expect, it } from "vitest";

import { FUND_SERIES_ID, parseFundPerformance } from "../data/fundPerformance";
import type { RawFundPerformanceRow } from "../data/types";

function row(over: Partial<RawFundPerformanceRow>): RawFundPerformanceRow {
  return {
    fund: "Alpha",
    quarter: "2026Q1",
    fund_return: "0.1",
    benchmark_return: "0.05",
    fund_cum_return: "0.1",
    benchmark_cum_return: "0.05",
    unpriced_weight: "0",
    ...over,
  };
}

const RAW = [
  row({}),
  row({
    quarter: "2026Q2",
    fund_return: "0.2",
    benchmark_return: "-0.02",
    fund_cum_return: "0.32",
    benchmark_cum_return: "0.029",
  }),
  row({ fund: "Beta", fund_return: "0.5", fund_cum_return: "0.5" }),
];

describe("parseFundPerformance", () => {
  const perf = parseFundPerformance(RAW, "Alpha");

  it("keeps only the requested fund's windows, in quarter order", () => {
    expect(perf?.quarters).toEqual(["2026Q1", "2026Q2"]);
  });

  it("starts the curve at the quarter before the first measured one", () => {
    expect(perf?.startQuarter).toBe("2025Q4");
    expect(parseFundPerformance([row({ quarter: "2025Q2" })], "Alpha")?.startQuarter).toBe(
      "2025Q1",
    );
  });

  it("returns a fund series and an S&P 500 series over the same windows", () => {
    const fund = perf?.series.find((s) => s.id === FUND_SERIES_ID);
    const spy = perf?.series.find((s) => s.id === "SPY");
    expect(fund?.type).toBe("strategy");
    // Readers see this label in the legend and tooltip: no internal acronyms.
    expect(fund?.label).toBe("Fund");
    expect(spy?.type).toBe("benchmark");
    expect(fund?.windows.map((w) => w.cumReturn)).toEqual([0.1, 0.32]);
    expect(spy?.windows.map((w) => w.cumReturn)).toEqual([0.05, 0.029]);
  });

  it("scores the fund against the index", () => {
    const fund = perf?.series.find((s) => s.id === FUND_SERIES_ID);
    expect(fund?.cumReturn).toBe(0.32);
    expect(fund?.excessPp).toBeCloseTo((0.32 - 0.029) * 100);
    expect(fund?.beats).toBe(2);
    expect(fund?.total).toBe(2);
  });

  it("drops benchmark windows the index could not price", () => {
    const blank = parseFundPerformance(
      [row({ benchmark_return: "", benchmark_cum_return: "" })],
      "Alpha",
    );
    expect(blank?.series.find((s) => s.id === "SPY")?.windows).toEqual([]);
    expect(blank?.series.find((s) => s.id === FUND_SERIES_ID)?.excessPp).toBeNull();
  });

  it("flags quarters where too much of the book went unpriced", () => {
    const flagged = parseFundPerformance(
      [row({}), row({ quarter: "2026Q2", unpriced_weight: "0.08" })],
      "Alpha",
    );
    expect(flagged?.lowCoverage).toEqual(["2026Q2"]);
    expect(perf?.lowCoverage).toEqual([]);
  });

  it("is null for a fund without any measured quarter", () => {
    expect(parseFundPerformance(RAW, "Gamma")).toBeNull();
  });
});
