import { Link } from "react-router";

import { SmartScoreBadge } from "@/components/SmartScoreBadge";
import { PanelTitle } from "@/components/ui/PanelTitle";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { learnItem } from "@/lib/routes";
import type { SmartScoreView } from "@/lib/smartScore";

const COMPONENTS: {
  key: keyof Omit<SmartScoreView, "smartScore">;
  label: string;
  meaning: string;
}[] = [
  { key: "breadth", label: "Breadth", meaning: "Tracked fund holders" },
  { key: "momentum", label: "Momentum", meaning: "Net fund buyers, not price momentum" },
  { key: "conviction", label: "Conviction", meaning: "Portfolio weights + new-entry bonus" },
];

/**
 * Relative institutional screen for one stock, using its quarter-analysis
 * universe. Source data can include non-quarterly updates in the latest
 * quarter. Keeps the single composite score beside the title, component
 * meanings visible, and methodology in the tooltip and FAQ. Renders nothing
 * without a score.
 */
export function SmartScorePanel({
  score,
  quarterLabel,
  loading = false,
}: {
  score: SmartScoreView | undefined;
  quarterLabel?: string;
  /** Holds the panel's footprint so the page below does not jump when the score arrives. */
  loading?: boolean;
}) {
  if (loading) {
    return (
      <div className="frame" aria-busy="true">
        <div className="frame-title h-10">
          <PanelTitle>Smart Score</PanelTitle>
          <span className="h-4 w-12 animate-pulse rounded-sm bg-muted" />
        </div>
        <div className="grid grid-cols-1 gap-x-6 divide-y divide-border px-3 pb-3 sm:grid-cols-3 sm:divide-y-0">
          {COMPONENTS.map(({ key, label }) => (
            <div key={key} className="py-2">
              <span className="text-sm font-medium leading-5">{label}</span>
              <span className="mt-1 block h-4 w-2/3 animate-pulse rounded-sm bg-muted" />
            </div>
          ))}
        </div>
        <span role="status" className="sr-only">
          Loading Smart Score…
        </span>
      </div>
    );
  }
  if (!score) return null;

  return (
    <div className="frame">
      <div className="frame-title h-10">
        <div className="flex items-center gap-2">
          <PanelTitle>Smart Score</PanelTitle>
          <InfoTooltip text="Relative to the selected quarter's analysis universe. Breadth, momentum and conviction combine into a 1–10 score; ties at one decimal follow the unrounded score. Latest-quarter data can include saved non-quarterly disclosures." />
        </div>
        <SmartScoreBadge score={score.smartScore} />
      </div>
      <div className="px-3 pb-3">
        <dl className="grid grid-cols-1 gap-x-6 divide-y divide-border sm:grid-cols-3 sm:divide-y-0">
          {COMPONENTS.map(({ key, label, meaning }) => (
            <div key={key} className="grid grid-cols-[1fr_auto] items-baseline gap-x-3 py-2">
              <dt className="text-sm font-medium leading-5">{label}</dt>
              <dd className="text-sm leading-5 tabular-nums">
                {score[key] === null ? "—" : Math.round(score[key])}
                <span className="ml-1 text-xs text-muted-foreground">/100</span>
              </dd>
              <dd className="col-span-2 text-xs leading-4 text-muted-foreground">{meaning}</dd>
            </div>
          ))}
        </dl>
        <p className="border-t border-border pt-2 text-xs leading-4 text-muted-foreground">
          {quarterLabel ? quarterLabel.replace("Q", " Q") : "Selected-quarter"} percentiles, not a
          return forecast.{" "}
          <Link
            to={learnItem("what-is-smart-score")}
            className="text-primary-text underline-offset-2 hover:underline"
          >
            Method FAQ
          </Link>
        </p>
      </div>
    </div>
  );
}
