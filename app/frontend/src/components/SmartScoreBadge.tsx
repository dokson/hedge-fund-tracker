import { Gauge } from "lucide-react";
import { smartScoreChipClass } from "@/lib/smartScore";

/**
 * Compact composite-score chip (1-10 scale), color-graded by bucket.
 * Shared by the stock header and any table row needing the at-a-glance score.
 * `size="sm"` drops the icon and "/10" suffix for dense, high-row-count tables
 * (e.g. the ranked Score tab) where the default chip is too tall/wide.
 */
export function SmartScoreBadge({
  score,
  title,
  size = "default",
}: {
  score: number;
  title?: string;
  size?: "default" | "sm";
}) {
  if (size === "sm") {
    return (
      <span
        className={`inline-flex items-center justify-center rounded-md border px-1.5 py-0.5 font-mono text-xs font-bold tabular-nums min-w-[2.75rem] ${smartScoreChipClass(score)}`}
        title={title ?? "Smart Score: composite of institutional signals"}
      >
        {score.toFixed(1)}
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${smartScoreChipClass(score)}`}
      title={title ?? "Smart Score: composite of institutional signals"}
    >
      <Gauge className="h-3.5 w-3.5" aria-hidden="true" />
      <span className="font-mono font-bold">{score.toFixed(1)}</span>
      <span className="opacity-70">/10</span>
    </span>
  );
}
