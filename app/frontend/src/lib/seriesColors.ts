/**
 * Shared color identity for the consensus strategies and benchmarks, so a
 * strategy keeps the same hue everywhere it appears (the /performance chart and
 * legend, and the QuarterlyTrends tabs). Keyed by canonical series/strategy id.
 */
export const SERIES_COLORS: Record<string, string> = {
  avg_portfolio: "hsl(175, 58%, 45%)",
  consensus: "hsl(217, 72%, 58%)",
  new_consensus: "hsl(265, 60%, 64%)",
  big_bets: "hsl(38, 88%, 55%)",
  increasing: "hsl(142, 60%, 45%)",
  decreasing: "hsl(0, 68%, 60%)",
  SPY: "hsl(215, 16%, 60%)",
  QQQ: "hsl(28, 22%, 58%)",
};

/** Deterministic, evenly-spread color for an arbitrary category key (e.g. a sector). */
export function hashColor(key: string, saturation = 55, lightness = 55): string {
  let hash = 0;
  for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) % 360;
  return `hsl(${hash}, ${saturation}%, ${lightness}%)`;
}

export function seriesColor(id: string): string {
  return SERIES_COLORS[id] ?? hashColor(id);
}
