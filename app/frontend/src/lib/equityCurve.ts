import type { PerfSeries } from "@/lib/dataService";

export type ChartPoint = { label: string; __band?: [number, number] } & Record<
  string,
  number | string
>;

/**
 * Horizontal space the chart keeps around its plot: the Y-axis labels on the
 * left and a small margin on the right.
 */
export const PLOT_INSET = { left: 48, right: 8 } as const;

/** Right margin reserved for the end-of-line labels when the chart is wide enough to show them. */
export const END_LABEL_INSET = 160;

/**
 * Vertical positions for end-of-line labels: each label stays as close to its line's
 * last point as possible while keeping at least `gap` pixels from its neighbours and
 * staying inside [top, bottom]. Returns positions in the input order.
 */
export function spreadLabels(ys: number[], gap: number, top: number, bottom: number): number[] {
  const order = ys.map((y, i) => ({ y, i })).sort((a, b) => a.y - b.y);
  const placed = order.map((o) => o.y);
  for (let k = 0; k < placed.length; k++) {
    placed[k] = Math.max(placed[k], k === 0 ? top : placed[k - 1] + gap);
  }
  for (let k = placed.length - 1; k >= 0; k--) {
    placed[k] = Math.min(placed[k], k === placed.length - 1 ? bottom : placed[k + 1] - gap);
  }
  const out: number[] = Array.from({ length: ys.length }, () => 0);
  order.forEach((o, k) => (out[o.i] = placed[k]));
  return out;
}

/**
 * Build the cumulative equity curve rows for a set of series.
 *
 * One row per quarter label (plus a flat 0% origin so every line starts
 * together); each series contributes its cumulative return in percentage points
 * under its own id key. Series with no window for a quarter simply omit that key.
 */
export function buildChartData(
  series: PerfSeries[],
  quarters: string[],
  originLabel = "Start",
  band?: { baseId: string; topId: string },
): ChartPoint[] {
  if (series.length === 0 || quarters.length === 0) return [];
  const withBand = (point: ChartPoint): ChartPoint => {
    if (!band) return point;
    const base = point[band.baseId];
    const top = point[band.topId];
    if (typeof base === "number" && typeof top === "number") point.__band = [base, top];
    return point;
  };
  const origin: ChartPoint = { label: originLabel };
  for (const s of series) origin[s.id] = 0;
  const points: ChartPoint[] = [withBand(origin)];
  for (const quarter of quarters) {
    const point: ChartPoint = { label: quarter };
    for (const s of series) {
      const window = s.windows.find((w) => w.quarterOut === quarter);
      if (window) point[s.id] = window.cumReturn * 100;
    }
    points.push(withBand(point));
  }
  return points;
}
