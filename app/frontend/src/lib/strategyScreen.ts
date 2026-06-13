import type { StockQuarterAnalysis } from "./dataService";
import type { StrategyDef } from "./strategies";

export interface ScreenHolding {
  ticker: string;
  company: string;
  /** Share of the strategy's portfolio (sums to 1.0 across holdings). */
  weight: number;
  /** Quarter-over-quarter change in aggregate shares held (%); 0 for new positions. */
  deltaPct: number;
  /** True when every holder opened the position this quarter (delta was Infinity). */
  isNew: boolean;
}

/**
 * Reconstruct a strategy's screen for one quarter, client-side, mirroring the
 * Python `select_screen` (filter → rank → top-N) and weighting by
 * Avg_Portfolio_Pct normalized to 1.0. Composition only — no prices/returns.
 *
 * The selection PARAMETERS come from the shared `StrategyDef` (pinned to the
 * Python specs by the strategies guard test); only the small filter/sort
 * algorithm is reimplemented here (no financial figures, so no drift risk).
 */
export function selectStrategyScreen(
  rows: StockQuarterAnalysis[],
  def: StrategyDef,
  minHolders: number,
): ScreenHolding[] {
  const key = def.sortKey as keyof StockQuarterAnalysis;
  let arr = def.minHolders ? rows.filter((r) => r.holderCount >= minHolders) : rows;
  if (def.excludeInfiniteDelta) arr = arr.filter((r) => Number.isFinite(r.delta));
  // The sign constraint applies to the ranking metric (matches Python select_screen).
  if (def.deltaSign === "positive") arr = arr.filter((r) => (r[key] as number) > 0);
  else if (def.deltaSign === "negative") arr = arr.filter((r) => (r[key] as number) < 0);

  arr = [...arr].sort((a, b) => {
    const va = a[key] as number;
    const vb = b[key] as number;
    if (!Number.isFinite(va) && !Number.isFinite(vb)) return 0;
    if (!Number.isFinite(va)) return def.ascending ? 1 : -1;
    if (!Number.isFinite(vb)) return def.ascending ? -1 : 1;
    return def.ascending ? va - vb : vb - va;
  });

  if (def.capped && def.topN != null) arr = arr.slice(0, def.topN);

  const total = arr.reduce((sum, r) => sum + (r.avgPortfolioPct || 0), 0);
  if (total <= 0) return [];
  return arr.map((r) => ({
    ticker: r.ticker,
    company: r.company,
    weight: (r.avgPortfolioPct || 0) / total,
    deltaPct: Number.isFinite(r.delta) ? r.delta : 0,
    isNew: !Number.isFinite(r.delta),
  }));
}
