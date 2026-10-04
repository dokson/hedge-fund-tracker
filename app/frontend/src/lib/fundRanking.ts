/**
 * Leaderboard of the tracked funds over database/fund_performance.csv. A fund
 * missing quarters (no measurable book at a window's start) is ranked on the
 * quarters it has, against the S&P 500 over those same quarters, and marked
 * partial: its excess compares, its raw return covers a shorter window.
 */

import { previousQuarter, UNPRICED_LIMIT } from "./data/fundPerformance";
import type { RawFundPerformanceRow } from "./data/types";

export interface RankedFund {
  fund: string;
  /** Compounded quarterly return over the window, as a fraction. */
  cumReturn: number;
  /** cumReturn minus the S&P 500's over the fund's own quarters. */
  excess: number;
  /** Quarters whose return beat the S&P 500's. */
  beats: number;
  /** Quarters the fund was measured on. */
  total: number;
  /** Measured on fewer quarters than the window. */
  partial: boolean;
  worstQuarter: number;
  /** Mean quarterly excess over its sample deviation; null when it never varies. */
  consistency: number | null;
  /** Largest share of the starting book left unpriced in any quarter. */
  maxUnpriced: number;
  lowCoverage: boolean;
}

export interface FundRanking {
  /** The common window, oldest first: the quarter each return ends in. */
  quarters: string[];
  /** The quarter whose 13F book the first return starts from; "" without data. */
  startQuarter: string;
  benchmarkReturn: number;
  funds: RankedFund[];
}

export type RankingKey = "cumReturn" | "excess" | "beats" | "worstQuarter" | "consistency";

function toNumber(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

const compound = (returns: readonly number[]) => returns.reduce((acc, r) => acc * (1 + r), 1) - 1;

function sampleDeviation(values: readonly number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((s, v) => s + v, 0) / values.length;
  const squares = values.reduce((s, v) => s + (v - mean) ** 2, 0);
  return Math.sqrt(squares / (values.length - 1));
}

/** Every fund ranked on the quarters present in the data, best cumulative return first. */
export function rankFunds(raw: readonly RawFundPerformanceRow[]): FundRanking {
  const quarters = [...new Set(raw.map((r) => r.quarter))].sort();
  const index = new Map<string, number>();
  const byFund = new Map<string, Map<string, RawFundPerformanceRow>>();
  for (const r of raw) {
    const benchmark = toNumber(r.benchmark_return);
    if (benchmark !== null && !index.has(r.quarter)) index.set(r.quarter, benchmark);
    const rows = byFund.get(r.fund) ?? new Map<string, RawFundPerformanceRow>();
    rows.set(r.quarter, r);
    byFund.set(r.fund, rows);
  }

  const indexReturns = quarters.map((q) => index.get(q) ?? 0);
  const funds: RankedFund[] = [];
  for (const [name, rows] of byFund) {
    const measured = quarters.flatMap((q) => {
      const value = toNumber(rows.get(q)?.fund_return ?? "");
      return value === null ? [] : [{ quarter: q, value }];
    });
    if (measured.length === 0) continue;
    const fundReturns = measured.map((m) => m.value);
    const ownIndex = measured.map((m) => index.get(m.quarter) ?? 0);
    const excessByQuarter = fundReturns.map((r, i) => r - (ownIndex[i] ?? 0));
    const deviation = sampleDeviation(excessByQuarter);
    const meanExcess = excessByQuarter.reduce((s, v) => s + v, 0) / excessByQuarter.length;
    const maxUnpriced = Math.max(
      ...measured.map((m) => toNumber(rows.get(m.quarter)?.unpriced_weight ?? "") ?? 0),
    );
    const cumReturn = compound(fundReturns);
    funds.push({
      fund: name,
      cumReturn,
      excess: cumReturn - compound(ownIndex),
      beats: excessByQuarter.filter((e) => e > 0).length,
      total: measured.length,
      partial: measured.length < quarters.length,
      worstQuarter: Math.min(...fundReturns),
      consistency: deviation > 1e-12 ? meanExcess / deviation : null,
      maxUnpriced,
      lowCoverage: maxUnpriced > UNPRICED_LIMIT,
    });
  }

  return {
    quarters,
    startQuarter: quarters[0] ? previousQuarter(quarters[0]) : "",
    benchmarkReturn: quarters.length ? compound(indexReturns) : 0,
    funds: sortRanking(funds, "cumReturn", "desc"),
  };
}

/** A sorted copy; funds without a value for the key go last in either direction. */
export function sortRanking(
  funds: readonly RankedFund[],
  key: RankingKey,
  dir: "asc" | "desc",
): RankedFund[] {
  const sign = dir === "desc" ? -1 : 1;
  return [...funds].sort((a, b) => {
    const x = a[key];
    const y = b[key];
    if (x === null) return y === null ? 0 : 1;
    if (y === null) return -1;
    return sign * (x - y) || a.fund.localeCompare(b.fund);
  });
}
