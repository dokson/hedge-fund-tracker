import type { CurvePoint } from "@/lib/fundRanking";
import { pctFrac } from "@/lib/performanceFormat";
import { BENCHMARK_DASH, seriesColor } from "@/lib/seriesColors";

/**
 * A small cumulative-return path against the benchmarks: the subject solid, green when it
 * ends ahead of the S&P 500 and red when behind; each benchmark in the colour and dash the
 * full charts draw it with (S&P 500 grey, Nasdaq-100 amber, when the data has it); zero as a
 * hairline.
 */
export function CurveSpark({ curve }: { curve: CurvePoint[] }) {
  const width = 96;
  const height = 28;
  const withNasdaq = curve.every((p) => p.nasdaq !== null);
  const values = curve.flatMap((p) => [p.fund, p.index, ...(withNasdaq ? [p.nasdaq ?? 0] : [])]);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const span = max - min || 1;
  const x = (i: number) => (curve.length > 1 ? (i / (curve.length - 1)) * width : width / 2);
  const y = (v: number) => height - 2 - ((v - min) / span) * (height - 4);
  const line = (pick: (p: CurvePoint) => number) =>
    curve.map((p, i) => `${x(i).toFixed(1)},${y(pick(p)).toFixed(1)}`).join(" ");
  const end = curve.at(-1) ?? { fund: 0, index: 0, nasdaq: null };
  const benchmark = (id: "SPY" | "QQQ", pick: (p: CurvePoint) => number) => (
    <polyline
      points={line(pick)}
      fill="none"
      stroke={seriesColor(id)}
      strokeWidth="1"
      strokeDasharray={BENCHMARK_DASH[id]}
      vectorEffect="non-scaling-stroke"
    />
  );
  return (
    <svg
      role="img"
      aria-label={`Cumulative ${pctFrac(end.fund)} against ${pctFrac(end.index)} for the S&P 500${
        withNasdaq && end.nasdaq !== null ? ` and ${pctFrac(end.nasdaq)} for the Nasdaq-100` : ""
      }`}
      viewBox={`0 0 ${width} ${height}`}
      className="ml-auto block h-7 w-full max-w-24 overflow-hidden"
    >
      <line
        x1="0"
        x2={width}
        y1={y(0)}
        y2={y(0)}
        className="stroke-border"
        strokeWidth="1"
        vectorEffect="non-scaling-stroke"
      />
      {withNasdaq && benchmark("QQQ", (p) => p.nasdaq ?? 0)}
      {benchmark("SPY", (p) => p.index)}
      <polyline
        points={line((p) => p.fund)}
        fill="none"
        className={
          end.fund >= end.index ? "stroke-[hsl(var(--positive))]" : "stroke-[hsl(var(--negative))]"
        }
        strokeWidth="1.5"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
