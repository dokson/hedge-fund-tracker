import { describe, it, expect } from "vitest";

import { buildChartData, spreadLabels } from "@/lib/equityCurve";
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

  it("keeps the supplied origin label and omits returns for missing windows", () => {
    const data = buildChartData([mkSeries("avg_portfolio", [0.2])], ["2025Q2", "2025Q3"], "2025Q1");
    expect(data[0]).toEqual({ label: "2025Q1", avg_portfolio: 0 });
    expect(data[2]).toEqual({ label: "2025Q3" });
  });

  it("shades the selected strategy against its benchmark without adding a missing return", () => {
    const data = buildChartData(
      [mkSeries("avg_portfolio", [0.2, -0.05]), mkSeries("SPY", [0.1])],
      ["2025Q2", "2025Q3"],
      "2025Q1",
      { baseId: "SPY", topId: "avg_portfolio" },
    );
    expect(data[0].__band).toEqual([0, 0]);
    expect(data[1].__band).toEqual([10, 20]);
    expect(data[2].__band).toBeUndefined();
    expect(data[2].avg_portfolio).toBeCloseTo(-5);
  });
});

describe("spreadLabels", () => {
  it("separates crowded end labels without reordering them or leaving the plot", () => {
    const placed = spreadLabels([100, 102, 98, 300, 299], 14, 10, 305);
    const byY = placed.map((y, i) => ({ y, i })).sort((a, b) => a.y - b.y);
    expect(byY.map((p) => p.i)).toEqual([2, 0, 1, 4, 3]);
    for (let k = 1; k < byY.length; k++) expect(byY[k].y - byY[k - 1].y).toBeGreaterThanOrEqual(14);
    expect(Math.min(...placed)).toBeGreaterThanOrEqual(10);
    expect(Math.max(...placed)).toBeLessThanOrEqual(305);
  });

  it("leaves labels that already have room on their line", () => {
    expect(spreadLabels([40, 120, 200], 14, 0, 300)).toEqual([40, 120, 200]);
  });
});
