/**
 * Strategy-backtest track record (database/performance.csv, long format).
 */

import { cachedFetch, fetchCSV } from "./fetch";
import type { PerfSeries, PerformanceData, RawPerformanceRow } from "./types";

/**
 * Sample standard deviation (Bessel-corrected); 0 with fewer than two values.
 */
function stdev(values: number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance = values.reduce((a, b) => a + (b - mean) ** 2, 0) / (values.length - 1);
  return Math.sqrt(variance);
}

/**
 * Group long-format performance rows into per-series track records.
 *
 * Each series (strategy or benchmark) keeps its ordered windows; strategies
 * also get cumulative excess vs the S&P 500 (percentage points) and a count of
 * windows that beat it. Kept pure (no fetch) so it is unit-testable.
 */
export function parsePerformanceRows(raw: RawPerformanceRow[]): PerformanceData {
  const bySeries = new Map<string, PerfSeries>();
  const quarters: string[] = [];
  for (const r of raw) {
    if (!quarters.includes(r.quarter_out)) quarters.push(r.quarter_out);
    let series = bySeries.get(r.series_id);
    if (!series) {
      series = {
        id: r.series_id,
        label: r.label,
        type: r.series_type === "benchmark" ? "benchmark" : "strategy",
        windows: [],
        cumReturn: 0,
        volatility: 0,
        excessPp: null,
        beats: 0,
        total: 0,
      };
      bySeries.set(r.series_id, series);
    }
    const excess = r.excess_return === "" ? null : parseFloat(r.excess_return);
    series.windows.push({
      quarterOut: r.quarter_out,
      windowReturn: parseFloat(r.window_return) || 0,
      cumReturn: parseFloat(r.cum_return) || 0,
      excessReturn: excess === null || Number.isNaN(excess) ? null : excess,
    });
  }

  const series = [...bySeries.values()];
  const spy = series.find((s) => s.id === "SPY");
  const spyCum = spy?.windows.at(-1)?.cumReturn ?? 0;
  for (const s of series) {
    s.total = s.windows.length;
    s.cumReturn = s.windows.at(-1)?.cumReturn ?? 0;
    s.volatility = stdev(s.windows.map((w) => w.windowReturn));
    if (s.type === "strategy") {
      s.excessPp = (s.cumReturn - spyCum) * 100;
      s.beats = s.windows.filter((w) => (w.excessReturn ?? 0) > 0).length;
    }
  }
  return {
    quarters,
    series,
    startDate: raw[0]?.entry_date ?? "",
    startQuarter: raw[0]?.quarter_in ?? "",
  };
}

export async function getPerformance(): Promise<PerformanceData> {
  return cachedFetch("performance", async () => {
    const raw = await fetchCSV<RawPerformanceRow>("/database/performance.csv", [
      "series_type",
      "series_id",
      "label",
      "quarter_in",
      "quarter_out",
      "entry_date",
      "window_return",
      "cum_return",
      "excess_return",
    ] satisfies readonly (keyof RawPerformanceRow)[]);
    return parsePerformanceRows(raw);
  });
}
