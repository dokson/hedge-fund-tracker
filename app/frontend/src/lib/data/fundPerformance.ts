/**
 * Per-fund quarterly Holding-Based Return vs the S&P 500
 * (database/fund_performance.csv, computed offline by gen_fund_performance.py).
 */

import { cachedFetch, fetchCSV } from "./fetch";
import type { PerfSeries, PerfWindow, RawFundPerformanceRow } from "./types";

/** Series id of the fund's own curve (the index keeps its "SPY" id). */
export const FUND_SERIES_ID = "fund";

/** Above this unpriced share of the book a quarter's estimate is flagged. */
export const UNPRICED_LIMIT = 0.05;

export interface FundPerformance {
  quarters: string[];
  series: PerfSeries[];
  /** Quarters whose unpriced weight exceeds UNPRICED_LIMIT. */
  lowCoverage: string[];
  /** The quarter whose end-of-quarter book the first return starts from (the 0% origin). */
  startQuarter: string;
}

/** `2025Q2` → `2025Q1`, `2025Q1` → `2024Q4`. */
export function previousQuarter(quarter: string): string {
  const year = Number(quarter.slice(0, 4));
  const q = Number(quarter.slice(5));
  return q === 1 ? `${year - 1}Q4` : `${year}Q${q - 1}`;
}

function toNumber(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function series(
  id: string,
  label: string,
  type: PerfSeries["type"],
  windows: PerfWindow[],
): PerfSeries {
  return {
    id,
    label,
    type,
    windows,
    cumReturn: windows.at(-1)?.cumReturn ?? 0,
    volatility: 0,
    excessPp: null,
    beats: 0,
    total: windows.length,
  };
}

/**
 * The fund's curve and the S&P 500's over the same quarters, shaped for the
 * equity-curve chart; null when the fund has no measured quarter. Pure, so it is
 * unit-testable without a fetch.
 */
export function parseFundPerformance(
  raw: readonly RawFundPerformanceRow[],
  fund: string,
): FundPerformance | null {
  const rows = raw
    .filter((r) => r.fund === fund)
    .sort((a, b) => a.quarter.localeCompare(b.quarter));
  if (rows.length === 0) return null;

  const fundWindows: PerfWindow[] = [];
  const indexWindows: PerfWindow[] = [];
  let beats = 0;
  for (const r of rows) {
    const fundReturn = toNumber(r.fund_return) ?? 0;
    const indexReturn = toNumber(r.benchmark_return);
    const indexCum = toNumber(r.benchmark_cum_return);
    fundWindows.push({
      quarterOut: r.quarter,
      windowReturn: fundReturn,
      cumReturn: toNumber(r.fund_cum_return) ?? 0,
      excessReturn: indexReturn === null ? null : fundReturn - indexReturn,
    });
    if (indexReturn !== null && indexCum !== null) {
      indexWindows.push({
        quarterOut: r.quarter,
        windowReturn: indexReturn,
        cumReturn: indexCum,
        excessReturn: null,
      });
      if (fundReturn > indexReturn) beats += 1;
    }
  }

  const fundSeries = series(FUND_SERIES_ID, "Fund", "strategy", fundWindows);
  const indexSeries = series("SPY", "S&P 500", "benchmark", indexWindows);
  const lastQuarter = fundWindows.at(-1)?.quarterOut;
  const indexAtEnd = indexWindows.find((w) => w.quarterOut === lastQuarter);
  fundSeries.excessPp = indexAtEnd ? (fundSeries.cumReturn - indexAtEnd.cumReturn) * 100 : null;
  fundSeries.beats = beats;

  return {
    quarters: rows.map((r) => r.quarter),
    series: [fundSeries, indexSeries],
    lowCoverage: rows
      .filter((r) => (toNumber(r.unpriced_weight) ?? 0) > UNPRICED_LIMIT)
      .map((r) => r.quarter),
    startQuarter: previousQuarter(rows[0].quarter),
  };
}

/** Every row of database/fund_performance.csv, fetched once and shared. */
export function getFundPerformanceRows(): Promise<RawFundPerformanceRow[]> {
  return cachedFetch("fundPerformance", () =>
    fetchCSV<RawFundPerformanceRow>("/database/fund_performance.csv", [
      "fund",
      "quarter",
      "fund_return",
      "benchmark_return",
      "fund_cum_return",
      "benchmark_cum_return",
      "unpriced_weight",
    ] satisfies readonly (keyof RawFundPerformanceRow)[]),
  );
}

export async function getFundPerformance(fund: string): Promise<FundPerformance | null> {
  return parseFundPerformance(await getFundPerformanceRows(), fund);
}
