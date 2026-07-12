import type { StockQuarterAnalysis } from "./dataService";

const HIGH_SCORE = 7.5;
const MID_SCORE = 4.5;

/** Percentile points added to Conviction per high-conviction new entry (pre-cap). */
const HC_ENTRY_CONVICTION_BONUS = 10;

/** The score and its component percentiles for one stock, all derived on the fly. */
export interface SmartScoreView {
  smartScore: number;
  breadth: number | null;
  momentum: number | null;
  conviction: number | null;
}

/**
 * Text color for a 1-10 composite score, shared by the badge and plain table cells.
 */
export function smartScoreToneClass(score: number): string {
  if (score >= HIGH_SCORE) return "text-[hsl(var(--positive))]";
  if (score >= MID_SCORE) return "text-amber-500";
  return "text-[hsl(var(--negative))]";
}

/**
 * Full chip styling (border + background + text) for the same score buckets.
 */
export function smartScoreChipClass(score: number): string {
  if (score >= HIGH_SCORE)
    return "border-[hsl(var(--positive))]/40 bg-[hsl(var(--positive))]/10 text-[hsl(var(--positive))]";
  if (score >= MID_SCORE) return "border-amber-500/40 bg-amber-500/10 text-amber-500";
  return "border-[hsl(var(--negative))]/40 bg-[hsl(var(--negative))]/10 text-[hsl(var(--negative))]";
}

/**
 * Fill color for a 0-100 percentile bar (Breadth/Momentum/Conviction), on the
 * same high/mid/low buckets as the composite score (thresholds scaled 1-10 → 0-100).
 */
export function percentileBarClass(value: number): string {
  if (value >= HIGH_SCORE * 10) return "bg-[hsl(var(--positive))]";
  if (value >= MID_SCORE * 10) return "bg-amber-500";
  return "bg-[hsl(var(--negative))]";
}

/**
 * Percentile ranks (0-100) with pandas `rank(pct=True)` semantics: ties take
 * their average 1-based rank; null entries stay null and don't count in n.
 */
function pctRank(values: (number | null)[]): (number | null)[] {
  const present = values
    .map((v, i) => [v, i] as const)
    .filter((pair): pair is readonly [number, number] => pair[0] !== null);
  const n = present.length;
  const out: (number | null)[] = values.map(() => null);
  const sorted = [...present].sort((a, b) => a[0] - b[0]);
  let i = 0;
  while (i < sorted.length) {
    let j = i;
    while (j + 1 < sorted.length && sorted[j + 1][0] === sorted[i][0]) j++;
    const avgRankPct = ((i + j + 2) / 2 / n) * 100;
    for (let k = i; k <= j; k++) out[sorted[k][1]] = avgRankPct;
    i = j + 1;
  }
  return out;
}

/**
 * Component percentiles + 1-10 composite for a set of quarter-analysis rows —
 * the TypeScript mirror of the Python `score_core` (backtest), computed on the
 * fly like every other consensus metric.
 */
export function smartScoreComponents(rows: StockQuarterAnalysis[]): SmartScoreView[] {
  const breadth = pctRank(rows.map((r) => r.holderCount));
  const momentum = pctRank(rows.map((r) => r.netBuyers));
  const conviction = pctRank(rows.map((r) => r.avgPortfolioPct)).map((v, i) =>
    v === null ? null : Math.min(100, v + rows[i].highConvictionCount * HC_ENTRY_CONVICTION_BONUS),
  );
  return rows.map((_, i) => {
    const parts = [breadth[i], momentum[i], conviction[i]].filter((v): v is number => v !== null);
    const mean = parts.reduce((s, v) => s + v, 0) / parts.length;
    return {
      smartScore: Math.round((1 + (9 * mean) / 100) * 10) / 10,
      breadth: breadth[i],
      momentum: momentum[i],
      conviction: conviction[i],
    };
  });
}

/**
 * The 1-10 composite alone (used by the /performance composition drill-down).
 */
export function smartScoreCore(rows: StockQuarterAnalysis[]): number[] {
  return smartScoreComponents(rows).map((c) => c.smartScore);
}

/**
 * Attach the on-the-fly score and component percentiles to quarter-analysis
 * rows, so every consumer (tabs, tables, stock page) reads the same numbers.
 */
export function withSmartScores<T extends StockQuarterAnalysis>(rows: T[]): T[] {
  const components = smartScoreComponents(rows);
  return rows.map((r, i) => ({
    ...r,
    smartScore: components[i].smartScore,
    scoreBreadth: components[i].breadth,
    scoreMomentum: components[i].momentum,
    scoreConviction: components[i].conviction,
  }));
}
