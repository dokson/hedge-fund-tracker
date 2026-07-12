import type { PerfSeries } from "@/lib/dataService";

export type ChartPoint = { label: string; __band?: [number, number] } & Record<
  string,
  number | string
>;

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
