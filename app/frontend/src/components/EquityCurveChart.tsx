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
import { buildChartData } from "@/lib/equityCurve";
import { BENCHMARK, GRID, NEUTRAL, seriesColor } from "@/lib/seriesColors";

const AXIS_TICK = { fill: NEUTRAL, fontSize: 11 };
import type { PerfSeries } from "@/lib/dataService";

const fmtPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(0)}%`;

function renderTooltip({ active, label, payload }: TooltipContentProps) {
  if (!active || !payload?.length) return null;
  const rows = payload.flatMap((p) =>
    typeof p.name === "string" && !p.name.startsWith("__")
      ? [{ name: p.name, value: Number(p.value ?? 0), color: p.color }]
      : [],
  );
  if (!rows.length) return null;
  const sorted = [...rows].sort((a, b) => b.value - a.value);
  return (
    <div className="rounded-md border border-border bg-popover px-2.5 py-2 text-xs text-foreground shadow-md">
      <div className="mb-1 text-muted-foreground">{label}</div>
      {sorted.map((p) => (
        <div
          key={p.name}
          className="flex justify-between gap-4 font-medium tabular-nums"
          style={{ color: p.color }}
        >
          <span>{p.name}</span>
          <span>{fmtPct(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

interface Props {
  series: PerfSeries[];
  quarters: string[];
  originLabel?: string;
  /** When set, shades the area between two series (e.g. a focused strategy vs its benchmark). */
  band?: { baseId: string; topId: string; color: string };
}

/**
 * Cumulative-return equity curve overlaying every supplied series (strategies
 * solid, benchmarks in grey). When `band` is set, the gap between the two named
 * series is shaded — used in single-strategy focus to show excess vs benchmark.
 */
export default function EquityCurveChart({ series, quarters, originLabel, band }: Props) {
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
    <div ref={containerRef} className="h-full min-h-[340px] w-full">
      {!size || data.length === 0 ? null : (
        <ComposedChart
          width={size.width}
          height={size.height}
          data={data}
          margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
        >
          <CartesianGrid stroke={GRID} strokeWidth={1} vertical={false} />
          <XAxis dataKey="label" tick={AXIS_TICK} axisLine={false} tickLine={false} />
          <YAxis
            tickFormatter={fmtPct}
            tick={AXIS_TICK}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <ReferenceLine y={0} stroke={NEUTRAL} strokeOpacity={0.4} />
          <Tooltip content={renderTooltip} />
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
              strokeWidth={2}
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
