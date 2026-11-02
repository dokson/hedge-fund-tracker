import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
  usePlotArea,
  useYAxisScale,
  type TooltipContentProps,
} from "recharts";
import { useElementSize } from "@/hooks/useElementSize";
import { buildChartData, END_LABEL_INSET, PLOT_INSET, spreadLabels } from "@/lib/equityCurve";
import { BENCHMARK, GRID, NEUTRAL, seriesColor } from "@/lib/seriesColors";
import { cn } from "@/lib/utils";
import type { PerfSeries } from "@/lib/dataService";

const AXIS_TICK = { fill: NEUTRAL, fontSize: 11 };
/** Below this chart width the labels would squeeze the plot; the legend carries the names. */
const END_LABEL_MIN_WIDTH = 560;

const fmtPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(0)}%`;
const fmtTooltipPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;

function renderTooltip({ active, label, payload }: TooltipContentProps) {
  if (!active || !payload?.length) return null;
  const rows = payload.flatMap((p) =>
    typeof p.name === "string" && !p.name.startsWith("__") && typeof p.value === "number"
      ? [{ name: p.name, value: p.value, color: p.color }]
      : [],
  );
  if (!rows.length) return null;
  const sorted = [...rows].sort((a, b) => b.value - a.value);
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2.5 text-xs text-popover-foreground shadow-md">
      <div className="mb-2 text-muted-foreground">{label} · Cumulative return</div>
      <dl className="space-y-1.5">
        {sorted.map((p) => (
          <div key={p.name} className="flex items-center justify-between gap-5 tabular-nums">
            <dt className="inline-flex items-center gap-2">
              <span
                aria-hidden="true"
                className="h-2 w-2 shrink-0"
                style={{ backgroundColor: p.color }}
              />
              {p.name}
            </dt>
            <dd className="font-medium">{fmtTooltipPct(p.value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/**
 * Names each line at its last point, so the curve reads without looking back at the
 * legend. Labels are spread vertically so converging lines never overlap.
 */
function EndLabels({ series, last }: { series: PerfSeries[]; last: Map<string, number> }) {
  const yScale = useYAxisScale();
  const plot = usePlotArea();
  if (!yScale || !plot) return null;
  const items = series.flatMap((s) => {
    const value = last.get(s.id);
    const y = value === undefined ? undefined : yScale(value);
    return value === undefined || y === undefined ? [] : [{ s, value, y }];
  });
  const ys = spreadLabels(
    items.map((it) => it.y),
    14,
    plot.y + 6,
    plot.y + plot.height - 2,
  );
  const x = plot.x + plot.width + 8;
  return (
    <g aria-hidden="true">
      {items.map((it, i) => (
        <text
          key={it.s.id}
          x={x}
          y={ys[i]}
          dominantBaseline="middle"
          fontSize={11}
          fill={it.s.type === "benchmark" ? NEUTRAL : seriesColor(it.s.id)}
        >
          <tspan fontWeight={600}>{fmtTooltipPct(it.value)}</tspan>
          <tspan dx={5} fill="hsl(var(--foreground))">
            {it.s.label}
          </tspan>
        </text>
      ))}
    </g>
  );
}

interface Props {
  series: PerfSeries[];
  quarters: string[];
  originLabel?: string;
  /** Override the plot's minimum height without changing shared chart geometry. */
  className?: string;
  /** When set, shades the area between two series (e.g. a focused strategy vs its benchmark). */
  band?: { baseId: string; topId: string; color: string };
  /** Name each line at its last point when the chart is wide enough (keeps the right inset otherwise). */
  endLabels?: boolean;
}

/**
 * Cumulative-return equity curve overlaying every supplied series (strategies
 * solid, benchmarks in grey). When `band` is set, the gap between the two named
 * series is shaded — used in single-strategy focus to show excess vs benchmark.
 */
export default function EquityCurveChart({
  series,
  quarters,
  originLabel,
  band,
  className,
  endLabels = false,
}: Props) {
  const [containerRef, size] = useElementSize();
  const data = buildChartData(
    series,
    quarters,
    originLabel,
    band ? { baseId: band.baseId, topId: band.topId } : undefined,
  );
  const showEndLabels = endLabels && !!size && size.width >= END_LABEL_MIN_WIDTH;
  const lastValues = new Map<string, number>();
  for (const point of data) {
    for (const s of series) {
      const value = point[s.id];
      if (typeof value === "number") lastValues.set(s.id, value);
    }
  }

  return (
    /* Fills a flex parent with a definite height; the min-h is the floor when
       the parent's height is content-driven (mobile stack). */
    <div ref={containerRef} className={cn("h-full min-h-[340px] w-full", className)}>
      {!size || data.length === 0 ? null : (
        <ComposedChart
          width={size.width}
          height={size.height}
          data={data}
          margin={{
            top: 8,
            right: showEndLabels ? END_LABEL_INSET : PLOT_INSET.right,
            left: 0,
            bottom: 0,
          }}
        >
          <CartesianGrid stroke={GRID} strokeWidth={1} vertical={false} />
          <XAxis dataKey="label" tick={AXIS_TICK} axisLine={false} tickLine={false} />
          <YAxis
            tickFormatter={fmtPct}
            tick={AXIS_TICK}
            axisLine={false}
            tickLine={false}
            width={PLOT_INSET.left}
          />
          <ReferenceLine y={0} stroke={NEUTRAL} strokeOpacity={0.4} />
          <Tooltip shared content={renderTooltip} />
          {band && (
            <Area
              type="monotone"
              dataKey="__band"
              fill={band.color}
              fillOpacity={0.16}
              stroke="none"
              tooltipType="none"
              isAnimationActive={false}
            />
          )}
          {series.map((s) => (
            <Line
              key={s.id}
              type="monotone"
              dataKey={s.id}
              name={s.label}
              stroke={s.type === "benchmark" ? BENCHMARK : seriesColor(s.id)}
              strokeWidth={s.type === "benchmark" ? 1.5 : 2.5}
              strokeDasharray={s.type === "benchmark" ? "4 4" : undefined}
              dot={false}
              isAnimationActive={false}
            />
          ))}
          {showEndLabels && <EndLabels series={series} last={lastValues} />}
        </ComposedChart>
      )}
    </div>
  );
}
