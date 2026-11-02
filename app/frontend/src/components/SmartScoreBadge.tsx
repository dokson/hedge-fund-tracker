import { smartScoreToneClass } from "@/lib/smartScore";

/**
 * Composite-score tag (1-10 scale), tinted by the score's tone.
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
      className={`inline-flex items-baseline justify-center gap-1 tabular-nums ${
        size === "sm" ? "min-w-[2.75rem]" : ""
      } ${smartScoreToneClass(score)}`}
      title={title ?? "Smart Score: relative institutional screen (1–10), not a return forecast"}
    >
      {score.toFixed(1)}
      {size === "default" && <span className="opacity-70">/10</span>}
    </span>
  );
}
