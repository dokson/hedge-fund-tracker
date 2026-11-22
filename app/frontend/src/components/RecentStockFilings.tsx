import { useId, useState } from "react";

import { FundCell } from "@/components/EntityLinks";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/LoadingState";
import { Panel } from "@/components/ui/Panel";
import { QueryState } from "@/components/ui/QueryState";
import { ChangeChip } from "@/components/ui/ChangeChip";
import { FaqLink } from "@/components/ui/TextLink";
import { useEnrichedNQFilings } from "@/hooks/useEnrichedNQFilings";
import { formatValue, parseValueString } from "@/lib/dataService";

const MAX_CARDS = 4;

/**
 * The stock's disclosures since the last 13F, newest first, as a row of cards: each 13D/G or
 * Form 4 with its date, the change it implies against that fund's latest 13F, the fund and
 * the position's value. Past the first row, the rest open in place.
 */
export function RecentStockFilings({ ticker, className }: { ticker: string; className?: string }) {
  const { data = [], isLoading, isError, error } = useEnrichedNQFilings();
  const [expanded, setExpanded] = useState(false);
  const listId = useId();
  const all = data
    .filter((f) => f.ticker === ticker)
    .toSorted((a, b) => b.filingDate.localeCompare(a.filingDate));
  const cards = expanded ? all : all.slice(0, MAX_CARDS);
  return (
    <Panel
      title="Since the last 13F"
      aside={
        all.length > MAX_CARDS ? (
          <Button
            variant="link"
            size="sm"
            aria-expanded={expanded}
            aria-controls={listId}
            onClick={() => setExpanded((open) => !open)}
            className="tap-target h-auto px-0 text-[13px]"
          >
            {expanded ? "Show fewer" : `Show all ${all.length}`}
          </Button>
        ) : (
          <span className="text-xs font-normal text-muted-foreground">13D/G and Form 4</span>
        )
      }
      className={className}
    >
      {isError ? (
        <QueryState isError error={error} title="Could not load the latest filings" />
      ) : isLoading ? (
        <LoadingState message="Loading filings…" size="sm" />
      ) : cards.length === 0 ? (
        <p className="px-3 py-2.5 text-[13px] text-muted-foreground">
          No 13D/G or Form 4 filing on {ticker} by a tracked fund since its last 13F.{" "}
          <FaqLink item="why-merge-non-quarterly">Why these filings count</FaqLink>
        </p>
      ) : (
        // Explicit role: Safari drops list semantics under `list-style: none`.
        // oxlint-disable-next-line jsx-a11y/no-redundant-roles
        <ol id={listId} role="list" className="grid gap-px bg-border sm:grid-cols-2 xl:grid-cols-4">
          {cards.map((f) => (
            <li
              key={`${f.fund}-${f.filingDate}-${f.shares}`}
              className="flex flex-col gap-1.5 bg-card px-3 py-2.5 text-[13px]"
            >
              <div className="flex items-center justify-between gap-2">
                <ChangeChip
                  change={f.deltaType}
                  suffix={
                    f.deltaPct !== null && f.deltaType !== "NEW" && f.deltaType !== "CLOSED"
                      ? ` ${f.deltaPct > 0 ? "+" : ""}${f.deltaPct.toFixed(0)}%`
                      : undefined
                  }
                />
                <time
                  dateTime={f.filingDate}
                  title={`Filed ${f.filingDate}`}
                  className="text-xs text-muted-foreground tabular-nums"
                >
                  {f.filingDate}
                </time>
              </div>
              <FundCell fundName={f.fund} />
              <span className="text-xs text-muted-foreground tabular-nums">
                Position {formatValue(parseValueString(f.value))}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}
