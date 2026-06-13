import { describe, it, expect } from "vitest";

import { buildChartData } from "@/lib/equityCurve";
import { seriesColor, SERIES_COLORS } from "@/lib/seriesColors";
import type { PerfSeries } from "@/lib/dataService";

const mkSeries = (id: string, cums: number[]): PerfSeries => ({
  id,
  label: id,
  type: id === "SPY" ? "benchmark" : "strategy",
  windows: cums.map((c, i) => ({
    quarterOut: `2025Q${i + 2}`,
    windowReturn: 0,
    cumReturn: c,
    excessReturn: null,
  })),
  cumReturn: cums.at(-1) ?? 0,
  volatility: 0,
  excessPp: null,
  beats: 0,
  total: cums.length,
});

describe("buildChartData", () => {
  it("returns empty when there are no series or quarters", () => {
    expect(buildChartData([], ["2025Q2"])).toEqual([]);
    expect(buildChartData([mkSeries("a", [0.1])], [])).toEqual([]);
  });

  it("prepends a 0 origin and maps cumulative returns to percentage points per series id", () => {
    const series = [mkSeries("avg_portfolio", [0.2, 0.32]), mkSeries("SPY", [0.1, 0.155])];
    const data = buildChartData(series, ["2025Q2", "2025Q3"]);
    expect(data.map((p) => p.label)).toEqual(["Start", "2025Q2", "2025Q3"]);
    expect(data[0]).toMatchObject({ avg_portfolio: 0, SPY: 0 });
    expect(data[1].avg_portfolio).toBeCloseTo(20, 6);
    expect(data[2].SPY).toBeCloseTo(15.5, 6);
  });
});

describe("seriesColor", () => {
  it("returns the fixed color for known series", () => {
    expect(seriesColor("avg_portfolio")).toBe(SERIES_COLORS.avg_portfolio);
  });

  it("falls back to a deterministic hue for unknown ids", () => {
    expect(seriesColor("zzz")).toMatch(/^hsl\(/);
  });
});
