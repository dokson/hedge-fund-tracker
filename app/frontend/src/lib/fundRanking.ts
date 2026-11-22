/**
 * Leaderboard of the tracked funds over database/fund_performance.csv. A fund
 * missing quarters (no measurable book at a window's start) is ranked on the
 * quarters it has, against the S&P 500 over those same quarters, and marked
 * partial: its excess compares, its raw return covers a shorter window. The
 * board ranks on the return per year, which puts records of different length
 * on one scale; a fund measured on less than a year has none and ranks last.
 */

import { previousQuarter, UNPRICED_LIMIT } from "./data/fundPerformance";
import { parseValueString } from "./data/format";
import { aggregateHoldingsByTicker } from "./data/quarterData";
import type { QuarterlyHolding, RawFundPerformanceRow } from "./data/types";

/**
 * One point of the cumulative path: the fund, the S&P 500 and the Nasdaq-100 over the same
 * quarters; `nasdaq` is null on every point when any of the fund's quarters lacks it.
 */
export interface CurvePoint {
  fund: number;
  index: number;
  nasdaq: number | null;
}

/** The fund's latest 13F book, read off its newest filed quarter. */
export interface PortfolioStats {
  /** Reported 13F value of the open positions. */
  aum: number;
  /** Open positions, a ticker's several CUSIPs counted once. */
  positions: number;
  /** Share of the book in its ten largest positions; null on an empty book. */
  top10Weight: number | null;
  /** The smaller of buys and sales in the quarter, over the book; null on an empty book. */
  turnover: number | null;
}

export interface RankedFund {
  fund: string;
  /** Compounded quarterly return over the window, as a fraction. */
  cumReturn: number;
  /** cumReturn per year over the fund's own quarters; null under a year of them. */
  annualReturn: number | null;
  /** cumReturn minus the S&P 500's over the fund's own quarters. */
  excess: number;
  /** cumReturn minus the Nasdaq-100's over the fund's own quarters; null without its data. */
  excessNasdaq: number | null;
  /** Quarters whose return beat the S&P 500's. */
  beats: number;
  /** Quarters the fund was measured on. */
  total: number;
  /** Measured on fewer quarters than the window. */
  partial: boolean;
  /** Mean quarterly excess over its sample deviation; null when it never varies. */
  consistency: number | null;
  /** Largest share of the starting book left unpriced in any quarter. */
  maxUnpriced: number;
  lowCoverage: boolean;
  /** Cumulative path from the starting book (0) through each observed quarter. */
  curve: CurvePoint[];
  /** Return in the window's last quarter; null when the fund has none for it. */
  lastReturn: number | null;
  /** lastReturn minus the S&P 500's that quarter. */
  lastExcess: number | null;
  /** Deviation of the quarterly returns, per year; null under a year of quarters. */
  volatility: number | null;
  /** Deepest fall from a running peak of the cumulative path, from the starting book (<= 0). */
  maxDrawdown: number;
  /** Filled once the latest 13F books are loaded. */
  aum?: number | null;
  positions?: number | null;
  top10Weight?: number | null;
  turnover?: number | null;
  /** The quarter the portfolio figures come from. */
  portfolioQuarter?: string;
}

export interface FundRanking {
  /** The common window, oldest first: the quarter each return ends in. */
  quarters: string[];
  /** The quarter whose 13F book the first return starts from; "" without data. */
  startQuarter: string;
  benchmarkReturn: number;
  funds: RankedFund[];
}

export type RankingKey =
  | "annualReturn"
  | "cumReturn"
  | "excess"
  | "excessNasdaq"
  | "lastReturn"
  | "beats"
  | "consistency"
  | "volatility"
  | "maxDrawdown"
  | "aum"
  | "positions"
  | "top10Weight"
  | "turnover";

/** Below a year of quarters a per-year figure extrapolates noise, so there is none. */
export const MIN_ANNUALIZED_QUARTERS = 4;

const annualize = (cumReturn: number, quarters: number) =>
  quarters < MIN_ANNUALIZED_QUARTERS ? null : (1 + cumReturn) ** (4 / quarters) - 1;

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

/** Every fund ranked on the quarters present in the data, best return per year first. */
export function rankFunds(raw: readonly RawFundPerformanceRow[]): FundRanking {
  const quarters = [...new Set(raw.map((r) => r.quarter))].sort();
  const index = new Map<string, number>();
  const nasdaq = new Map<string, number>();
  const byFund = new Map<string, Map<string, RawFundPerformanceRow>>();
  for (const r of raw) {
    const benchmark = toNumber(r.benchmark_return);
    if (benchmark !== null && !index.has(r.quarter)) index.set(r.quarter, benchmark);
    const second = toNumber(r.nasdaq_return ?? "");
    if (second !== null && !nasdaq.has(r.quarter)) nasdaq.set(r.quarter, second);
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
    const hasNasdaq = measured.every((m) => nasdaq.has(m.quarter));
    const ownNasdaq = measured.map((m) => nasdaq.get(m.quarter) ?? 0);
    const curve: CurvePoint[] = [{ fund: 0, index: 0, nasdaq: hasNasdaq ? 0 : null }];
    let fundLevel = 1;
    let indexLevel = 1;
    let nasdaqLevel = 1;
    let peak = 1;
    let maxDrawdown = 0;
    for (const [i, r] of fundReturns.entries()) {
      fundLevel *= 1 + r;
      indexLevel *= 1 + (ownIndex[i] ?? 0);
      nasdaqLevel *= 1 + (ownNasdaq[i] ?? 0);
      peak = Math.max(peak, fundLevel);
      maxDrawdown = Math.min(maxDrawdown, fundLevel / peak - 1);
      curve.push({
        fund: fundLevel - 1,
        index: indexLevel - 1,
        nasdaq: hasNasdaq ? nasdaqLevel - 1 : null,
      });
    }
    const lastQuarter = quarters.at(-1);
    const last = measured.at(-1);
    const lastReturn = last && last.quarter === lastQuarter ? last.value : null;
    funds.push({
      fund: name,
      cumReturn,
      annualReturn: annualize(cumReturn, measured.length),
      excess: cumReturn - compound(ownIndex),
      excessNasdaq: hasNasdaq ? cumReturn - compound(ownNasdaq) : null,
      beats: excessByQuarter.filter((e) => e > 0).length,
      total: measured.length,
      partial: measured.length < quarters.length,
      consistency: deviation > 1e-12 ? meanExcess / deviation : null,
      maxUnpriced,
      lowCoverage: maxUnpriced > UNPRICED_LIMIT,
      curve,
      lastReturn,
      lastExcess:
        lastReturn === null || lastQuarter === undefined
          ? null
          : lastReturn - (index.get(lastQuarter) ?? 0),
      volatility:
        measured.length < MIN_ANNUALIZED_QUARTERS ? null : sampleDeviation(fundReturns) * 2,
      maxDrawdown,
    });
  }

  return {
    quarters,
    startQuarter: quarters[0] ? previousQuarter(quarters[0]) : "",
    benchmarkReturn: quarters.length ? compound(indexReturns) : 0,
    funds: sortRanking(funds, "annualReturn", "desc"),
  };
}

/** Size, concentration and trading of one 13F book (`getFundQuarterlyHoldings` rows). */
export function portfolioStats(holdings: QuarterlyHolding[]): PortfolioStats {
  const byTicker = aggregateHoldingsByTicker(holdings);
  const values = byTicker.map((h) => parseValueString(h.value)).filter((v) => v > 0);
  const aum = values.reduce((s, v) => s + v, 0);
  let bought = 0;
  let sold = 0;
  for (const h of byTicker) {
    const traded = parseValueString(h.deltaValue);
    if (traded > 0) bought += traded;
    else sold -= traded;
  }
  const top10 = values
    .toSorted((a, b) => b - a)
    .slice(0, 10)
    .reduce((s, v) => s + v, 0);
  return {
    aum,
    positions: values.length,
    top10Weight: aum > 0 ? top10 / aum : null,
    turnover: aum > 0 ? Math.min(bought, sold) / aum : null,
  };
}

/** A sorted copy; funds without a value for the key go last in either direction. */
export function sortRanking(
  funds: readonly RankedFund[],
  key: RankingKey,
  dir: "asc" | "desc",
): RankedFund[] {
  const sign = dir === "desc" ? -1 : 1;
  return funds.toSorted((a, b) => {
    const x = a[key];
    const y = b[key];
    if (x == null) return y == null ? 0 : 1;
    if (y == null) return -1;
    return sign * (x - y) || a.fund.localeCompare(b.fund);
  });
}
