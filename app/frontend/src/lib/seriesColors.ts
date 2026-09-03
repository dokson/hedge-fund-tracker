/**
 * Chart colour tokens. Every value resolves through the theme's HSL triples,
 * so a chart re-themes with the page and never carries a hue of its own.
 */
export const POSITIVE = "hsl(var(--positive))";
export const NEGATIVE = "hsl(var(--negative))";
export const NEUTRAL = "hsl(var(--muted-foreground))";
/** Benchmarks are neutral grey and dashed, never a hue of their own. */
export const BENCHMARK = NEUTRAL;
export const GRID = "hsl(var(--border))";

export const CHART_PALETTE: readonly string[] = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
];

/** A token at reduced alpha: the treemap ramp is opacity steps of one hue. */
export function tokenAlpha(
  token: "positive" | "negative" | "muted" | "muted-foreground",
  alpha: number,
): string {
  return `hsl(var(--${token}) / ${alpha})`;
}

/**
 * Shared color identity for the consensus strategies and benchmarks, so a
 * strategy keeps the same hue everywhere it appears (the /performance chart and
 * legend, and the QuarterlyTrends tabs). Keyed by canonical series/strategy id.
 * Benchmarks are neutral; increasing/decreasing take the delta tokens.
 */
export const SERIES_COLORS: Record<string, string> = {
  avg_portfolio: CHART_PALETTE[0],
  consensus: CHART_PALETTE[3],
  new_consensus: CHART_PALETTE[4],
  big_bets: "hsl(var(--foreground))",
  increasing: POSITIVE,
  decreasing: NEGATIVE,
  SPY: BENCHMARK,
  QQQ: BENCHMARK,
};

/** Deterministic palette entry for an arbitrary category key (e.g. a sector). */
export function hashColor(key: string): string {
  let hash = 0;
  for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) % 360;
  return CHART_PALETTE[hash % CHART_PALETTE.length];
}

export function seriesColor(id: string): string {
  return SERIES_COLORS[id] ?? hashColor(id);
}

/** Recharts `isAnimationActive`: off when the OS asks for reduced motion. */
export function chartAnimationActive(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  return !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
