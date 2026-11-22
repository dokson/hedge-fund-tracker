import { cn } from "@/lib/utils";

/**
 * The key of a chart series in a legend, tooltip or KPI label: a colour square, or with
 * `dash` a short line drawn the way the chart draws that series (benchmarks are dashed).
 */
export function SeriesSwatch({
  color,
  dash,
  className,
}: {
  color?: string;
  dash?: string;
  className?: string;
}) {
  if (dash) {
    return (
      <svg
        aria-hidden="true"
        viewBox="0 0 18 4"
        className={cn("inline-block h-1 w-[18px] shrink-0 overflow-visible", className)}
      >
        <line x1="0" x2="18" y1="2" y2="2" stroke={color} strokeWidth="2" strokeDasharray={dash} />
      </svg>
    );
  }
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block h-2 w-2 shrink-0", className)}
      style={{ backgroundColor: color }}
    />
  );
}
