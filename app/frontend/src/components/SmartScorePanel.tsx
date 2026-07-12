import { SmartScoreBadge } from "@/components/SmartScoreBadge";
import { percentileBarClass, type SmartScoreView } from "@/lib/smartScore";

const COMPONENTS: { key: keyof Omit<SmartScoreView, "smartScore">; label: string }[] = [
  { key: "breadth", label: "Breadth" },
  { key: "momentum", label: "Momentum" },
  { key: "conviction", label: "Conviction" },
];

/**
 * Institutional smart-score breakdown for one stock: the 1-10 composite plus
 * the three component percentiles it blends, computed on the fly for the
 * selected quarter. Renders nothing without a score.
 */
export function SmartScorePanel({
  score,
  quarterLabel,
}: {
  score: SmartScoreView | undefined;
  quarterLabel?: string;
}) {
  if (!score) return null;

  return (
    <div className="surface p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="section-title text-sm">Smart Score</h3>
        <SmartScoreBadge score={score.smartScore} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-6 gap-y-1.5">
        {COMPONENTS.map(({ key, label }) => {
          const value = score[key];
          return (
            <div key={key} className="flex items-center gap-2">
              <span className="w-20 shrink-0 text-[11px] text-muted-foreground">{label}</span>
              <span className="block h-1.5 flex-1 rounded-full bg-muted">
                {value !== null && (
                  <span
                    className={`block h-full rounded-full ${percentileBarClass(value)}`}
                    style={{ width: `${value}%` }}
                  />
                )}
              </span>
              <span className="w-9 shrink-0 text-right font-mono text-[11px]">
                {value === null ? "—" : Math.round(value)}
              </span>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[11px] text-muted-foreground">
        Percentiles vs the {quarterLabel ? `${quarterLabel.replace("Q", " Q")} ` : "current "}
        tracked universe (13F + recent 13D/G · Form 4) · institutional signals only
      </p>
    </div>
  );
}
