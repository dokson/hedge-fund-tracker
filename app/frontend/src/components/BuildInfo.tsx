import { useState } from "react";
import { Check, Hourglass } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { APP_VERSION } from "@/lib/config";

const label = (quarter: string) => quarter.replace("Q", " Q");

/**
 * The baseline's state: current when it is the newest quarter on file, filling when a newer
 * quarter has some filings but not yet enough to be the baseline.
 */
function useBaseline() {
  const { quarters, latestQuarter } = useAvailableQuarters();
  const newest = quarters.at(-1);
  const filling = latestQuarter && newest && newest > latestQuarter ? newest : undefined;
  return { latestQuarter, filling };
}

/** The state mark: green when current, amber while a newer quarter fills in; never alone. */
function StateMark({ filling }: { filling: string | undefined }) {
  return filling ? (
    <Hourglass aria-hidden="true" className="inline h-3 w-3 shrink-0 text-warning" />
  ) : (
    <Check aria-hidden="true" className="inline h-3 w-3 shrink-0 text-positive" />
  );
}

/**
 * What the data is and which build shows it: the 13F baseline (with its state), the source,
 * the version and the maker. Lives once, at the foot of the navigation (sidebar and phone
 * menu), never in the top bar. `compact` is the collapsed rail: the mark alone, its meaning
 * in the accessible name and the tooltip.
 */
export function BuildInfo({ compact = false }: { compact?: boolean }) {
  const { latestQuarter, filling } = useBaseline();
  const [tooltipOpen, setTooltipOpen] = useState(false);
  const state = latestQuarter
    ? `13F baseline ${label(latestQuarter)}${filling ? `, ${label(filling)} filling in` : ", current"}`
    : "";

  if (compact) {
    if (!latestQuarter) return null;
    return (
      <Tooltip open={tooltipOpen} onOpenChange={setTooltipOpen}>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={state}
            onClick={() => setTooltipOpen(true)}
            className="flex min-h-6 min-w-6 items-center justify-center rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          >
            <StateMark filling={filling} />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right">{state}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <dl className="status-line space-y-0.5 text-xs">
      {latestQuarter && (
        <div>
          <dt className="k inline">
            <StateMark filling={filling} /> 13F baseline
          </dt>{" "}
          <dd className="inline">{label(latestQuarter)}</dd>
          {filling && (
            <dd className="inline text-muted-foreground">, {label(filling)} filling in</dd>
          )}
        </div>
      )}
      <div className="truncate">
        <dt className="k inline">Source</dt>{" "}
        <dd className="inline">
          {/* The source is a citation: linked, so every figure can be checked at its origin. */}
          <a
            href="https://www.sec.gov/edgar/search/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2 hover:text-foreground"
          >
            SEC EDGAR
          </a>
        </dd>
      </div>
      <div className="truncate text-muted-foreground">
        <dt className="sr-only">Version</dt>
        <dd className="inline">
          v{APP_VERSION}, ©{" "}
          <a
            href="https://www.coalesce.coach/en"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="COalesCE website"
            className="underline underline-offset-2 hover:text-foreground"
          >
            COalesCE
          </a>
        </dd>
      </div>
    </dl>
  );
}
