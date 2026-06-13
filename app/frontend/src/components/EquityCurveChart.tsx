import { Area, ComposedChart, Line, ReferenceLine, Tooltip, XAxis, YAxis } from "recharts";
import { useElementSize } from "@/hooks/useElementSize";
import { buildChartData } from "@/lib/equityCurve";
import { seriesColor } from "@/lib/seriesColors";
import type { PerfSeries } from "@/lib/dataService";

const fmtPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(0)}%`;

interface TooltipProps {
  active?: boolean;
  label?: string;
  payload?: Array<{ name?: string; value?: number; color?: string }>;
}

function renderTooltip({ active, label, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p) => p.name && !p.name.startsWith("__"));
  if (!rows.length) return null;
  const sorted = [...rows].sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
  return (
    <div
      style={{
        background: "hsl(var(--popover))",
        border: "1px solid hsl(var(--border))",
        borderRadius: 8,
        padding: "8px 10px",
        fontSize: 12,
        boxShadow: "0 4px 16px rgba(0,0,0,0.18)",
      }}
    >
      <div style={{ color: "hsl(var(--muted-foreground))", marginBottom: 4 }}>{label}</div>
      {sorted.map((p) => (
        <div
          key={p.name}
          style={{
            color: p.color,
            fontWeight: 600,
            fontFamily: "monospace",
            display: "flex",
            justifyContent: "space-between",
            gap: 16,
          }}
        >
          <span>{p.name}</span>
          <span>{fmtPct(p.value ?? 0)}</span>
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
    <div ref={containerRef} className="h-[340px] w-full">
      {!size || data.length === 0 ? null : (
        <ComposedChart
          width={size.width}
          height={size.height}
          data={data}
          margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
        >
          <XAxis
            dataKey="label"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tickFormatter={fmtPct}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeOpacity={0.4} />
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
              stroke={seriesColor(s.id)}
              strokeWidth={s.type === "benchmark" ? 2 : 2.5}
              strokeOpacity={s.type === "benchmark" ? 0.85 : 1}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </ComposedChart>
      )}
    </div>
  );
}
