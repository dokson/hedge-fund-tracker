import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";
import { useElementSize } from "@/hooks/useElementSize";
import { buildChartData, PLOT_INSET } from "@/lib/equityCurve";
import { BENCHMARK, GRID, NEUTRAL, seriesColor } from "@/lib/seriesColors";
import { cn } from "@/lib/utils";

const AXIS_TICK = { fill: NEUTRAL, fontSize: 11 };
import type { PerfSeries } from "@/lib/dataService";

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

interface Props {
  series: PerfSeries[];
  quarters: string[];
  originLabel?: string;
  /** Override the plot's minimum height without changing shared chart geometry. */
  className?: string;
  /** When set, shades the area between two series (e.g. a focused strategy vs its benchmark). */
  band?: { baseId: string; topId: string; color: string };
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
}: Props) {
  const [containerRef, size] = useElementSize();
  const data = buildChartData(
    series,
    quarters,
    originLabel,
    band ? { baseId: band.baseId, topId: band.topId } : undefined,
  );

  return (
    /* Fills a flex parent with a definite height; the min-h is the floor when
       the parent's height is content-driven (mobile stack). */
    <div ref={containerRef} className={cn("h-full min-h-[340px] w-full", className)}>
      {!size || data.length === 0 ? null : (
        <ComposedChart
          width={size.width}
          height={size.height}
          data={data}
          margin={{ top: 8, right: PLOT_INSET.right, left: 0, bottom: 0 }}
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
        </ComposedChart>
      )}
    </div>
  );
}
