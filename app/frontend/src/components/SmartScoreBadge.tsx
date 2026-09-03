import { smartScoreToneClass } from "@/lib/smartScore";

/**
 * Composite-score tag (1-10 scale) as a tinted pill in the score's tone.
 * `size="sm"` drops the "/10" suffix for dense tables.
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
  return (
    <span
      className={`chip justify-center gap-1 tabular-nums ${
        size === "sm" ? "min-w-[2.75rem]" : ""
      } ${smartScoreToneClass(score)}`}
      title={title ?? "Smart Score: composite of institutional signals"}
    >
      {score.toFixed(1)}
      {size === "default" && <span className="opacity-70">/10</span>}
    </span>
  );
}
