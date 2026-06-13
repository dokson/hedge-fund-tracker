import { describe, expect, it } from "vitest";

import { parsePerformanceRows, type RawPerformanceRow } from "../dataService";

const row = (over: Partial<RawPerformanceRow>): RawPerformanceRow => ({
  series_type: "strategy",
  series_id: "avg_portfolio",
  label: "Avg Portfolio",
  quarter_in: "2025Q1",
  quarter_out: "2025Q2",
  entry_date: "2025-05-15",
  exit_date: "2025-08-14",
  n_stocks: "50",
  window_return: "0",
  cum_return: "0",
  excess_return: "",
  turnover: "0",
  ...over,
});

const RAW: RawPerformanceRow[] = [
  row({
    series_type: "benchmark",
    series_id: "SPY",
    label: "S&P 500",
    quarter_out: "2025Q2",
    window_return: "0.1",
    cum_return: "0.1",
    excess_return: "",
  }),
  row({ quarter_out: "2025Q2", window_return: "0.2", cum_return: "0.2", excess_return: "0.1" }),
  row({
    series_type: "benchmark",
    series_id: "SPY",
    label: "S&P 500",
    quarter_out: "2025Q3",
    window_return: "0.05",
    cum_return: "0.155",
    excess_return: "",
  }),
  row({ quarter_out: "2025Q3", window_return: "0.1", cum_return: "0.32", excess_return: "0.05" }),
];

describe("parsePerformanceRows", () => {
  it("groups rows into per-series track records", () => {
    const { series, quarters } = parsePerformanceRows(RAW);
    expect(quarters).toEqual(["2025Q2", "2025Q3"]);
    expect(series.map((s) => s.id).sort()).toEqual(["SPY", "avg_portfolio"]);
    const avg = series.find((s) => s.id === "avg_portfolio")!;
    expect(avg.windows).toHaveLength(2);
    expect(avg.cumReturn).toBeCloseTo(0.32, 6);
  });

  it("computes cumulative excess vs S&P and win count for strategies", () => {
    const { series } = parsePerformanceRows(RAW);
    const avg = series.find((s) => s.id === "avg_portfolio")!;
    // (0.32 - 0.155) * 100
    expect(avg.excessPp).toBeCloseTo(16.5, 4);
    expect(avg.beats).toBe(2);
    expect(avg.total).toBe(2);
    // sample stdev of [0.2, 0.1]
    expect(avg.volatility).toBeCloseTo(0.070711, 5);
  });

  it("leaves benchmark series without excess/beats", () => {
    const { series } = parsePerformanceRows(RAW);
    const spy = series.find((s) => s.id === "SPY")!;
    expect(spy.type).toBe("benchmark");
    expect(spy.excessPp).toBeNull();
    expect(spy.cumReturn).toBeCloseTo(0.155, 6);
  });
});
