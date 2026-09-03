import { SmartScoreBadge } from "@/components/SmartScoreBadge";
import { PanelTitle } from "@/components/ui/PanelTitle";
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
    <div className="frame">
      <div className="frame-title">
        {/* h2: the panel sits directly under the page h1 on /stock, so an h3
            here skipped a level (WCAG 1.3.1). */}
        <PanelTitle>Smart Score</PanelTitle>
        <SmartScoreBadge score={score.smartScore} />
      </div>
      <div className="p-3">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-6 gap-y-1.5">
          {COMPONENTS.map(({ key, label }) => {
            const value = score[key];
            return (
              <div key={key} className="flex items-center gap-2">
                <span className="w-20 shrink-0 metric-label">{label}</span>
                <span className="block h-1.5 flex-1 rounded-sm bg-muted" aria-hidden="true">
                  {value !== null && (
                    <span
                      className={`block h-full rounded-sm ${percentileBarClass(value)}`}
                      style={{ width: `${value}%` }}
                    />
                  )}
                </span>
                <span className="w-9 shrink-0 text-right text-xs tabular-nums">
                  {value === null ? "—" : Math.round(value)}
                </span>
              </div>
            );
          })}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Percentiles vs the {quarterLabel ? `${quarterLabel.replace("Q", " Q")} ` : "current "}
          tracked universe (13F + recent 13D/G · Form 4) · institutional signals only
        </p>
      </div>
    </div>
  );
}
