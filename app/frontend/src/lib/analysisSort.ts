import type { NumericStockKey, StockQuarterAnalysis } from "./data/types";
import { compareBySmartScore } from "./smartScore";

/**
 * Rows ordered by one numeric analysis field, the single ordering behind the Quarterly Trends
 * tables and the strategy screens. Non-finite values (an all-new stock's infinite delta) lead a
 * descending order and trail an ascending one. Smart Score ties on the displayed one-decimal
 * score are broken by the unrounded composite, as the Python backtest ranks them.
 */
export function sortAnalysisRows<T extends StockQuarterAnalysis>(
  rows: readonly T[],
  key: NumericStockKey,
  dir: "asc" | "desc",
): T[] {
  const sign = dir === "desc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    if (key === "smartScore") return sign * compareBySmartScore(a, b);
    const va = a[key] ?? NaN;
    const vb = b[key] ?? NaN;
    if (!Number.isFinite(va) && !Number.isFinite(vb)) return 0;
    if (!Number.isFinite(va)) return -sign;
    if (!Number.isFinite(vb)) return sign;
    return sign * (vb - va);
  });
}
