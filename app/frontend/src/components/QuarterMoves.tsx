import type { ReactNode } from "react";
import {
  Check,
  CirclePlus,
  CircleX,
  TrendingDown,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

import { FundCell, TickerLink } from "@/components/EntityLinks";
import { Panel } from "@/components/ui/Panel";
import type { FundTickerHolding, QuarterlyHolding } from "@/lib/dataService";
import { formatValue, parseValueString } from "@/lib/dataService";
import { pctFrac } from "@/lib/performanceFormat";
import { toneClass } from "@/lib/tone";
import { cn } from "@/lib/utils";

import { HOLDER_MOVE_PICK, type MoveFilter } from "@/lib/moves";

const TOP_ITEMS = 5;

/** The four kinds of move, in reading order: what came in, what grew, what shrank, what left. */
const KINDS: { key: MoveFilter; label: string; icon: LucideIcon; tone: "positive" | "negative" }[] =
  [
    { key: "new", label: "New positions", icon: CirclePlus, tone: "positive" },
    { key: "increased", label: "Added to", icon: TrendingUp, tone: "positive" },
    { key: "decreased", label: "Trimmed", icon: TrendingDown, tone: "negative" },
    { key: "closed", label: "Sold out", icon: CircleX, tone: "negative" },
  ];

/** Buys read green and sales red at a glance: the label, its icon and a faint wash of the row. */
const TONE = {
  positive: { text: "text-positive", wash: "bg-[hsl(var(--positive)/0.06)]" },
  negative: { text: "text-negative", wash: "bg-[hsl(var(--negative)/0.06)]" },
} as const;

/**
 * The frame of a quarter's moves: each kind of change with its count (a toggle that filters
 * the table below) and its largest items. The fund page lists tickers, the stock page funds.
 */
function MovesPanel({
  title,
  quarterLabel,
  groups,
  active,
  onToggle,
  layout,
  className,
}: {
  title: string;
  quarterLabel: string;
  groups: Record<MoveFilter, { count: number; items: ReactNode[] }>;
  active: MoveFilter | "all";
  onToggle: (key: MoveFilter) => void;
  /**
   * `wrap`: groups stacked, short items (tickers) wrapping in a line. `columns`: the four
   * groups side by side (two on tablets, stacked on phones), one item per line (funds).
   */
  layout: "wrap" | "columns";
  className?: string;
}) {
  return (
    <Panel
      title={title}
      aside={<span className="text-xs font-normal text-muted-foreground">{quarterLabel}</span>}
      className={className}
    >
      <ul
        // Explicit role: Safari drops list semantics under `list-style: none`.
        // oxlint-disable-next-line jsx-a11y/no-redundant-roles
        role="list"
        // One column on phones (four implicit ones overflowed at 320px), dividers at 3:1.
        className={
          layout === "wrap"
            ? "divide-y divide-border"
            : "grid grid-cols-1 gap-px bg-input sm:grid-cols-2 xl:grid-cols-4"
        }
      >
        {KINDS.map((k) => {
          const { count, items } = groups[k.key];
          const isActive = active === k.key;
          return (
            // The card ground under the wash: in `columns` the hairline gaps show the border.
            <li key={k.key} className="bg-card">
              <div className={cn("h-full px-3 py-2.5", TONE[k.tone].wash)}>
                <button
                  type="button"
                  aria-pressed={isActive}
                  onClick={() => onToggle(k.key)}
                  className={cn(
                    "flex min-h-7 w-full items-center gap-1.5 rounded-sm text-left text-[13px] font-semibold underline-offset-2 hover:underline",
                    TONE[k.tone].text,
                  )}
                  title={`Show only ${k.label.toLowerCase()} in the table`}
                >
                  {isActive ? (
                    <Check aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                  ) : (
                    <k.icon aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                  )}
                  {k.label}
                  <span className="ml-auto tabular-nums">{count}</span>
                </button>
                {items.length > 0 && (
                  <div
                    className={cn(
                      "mt-1",
                      layout === "wrap"
                        ? "flex flex-wrap gap-x-4 gap-y-1 pl-5"
                        : "flex flex-col gap-1.5",
                    )}
                  >
                    {items}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

/** Pick each kind's rows and keep the largest by the money that moved. */
function groupMoves<T>(
  rows: readonly T[],
  pick: Record<MoveFilter, (row: T) => boolean>,
  size: Record<MoveFilter, (row: T) => number>,
  render: (row: T, kind: MoveFilter) => ReactNode,
): Record<MoveFilter, { count: number; items: ReactNode[] }> {
  const out = {} as Record<MoveFilter, { count: number; items: ReactNode[] }>;
  for (const { key } of KINDS) {
    const matched = rows.filter(pick[key]);
    out[key] = {
      count: matched.length,
      items: matched
        .toSorted((a, b) => size[key](b) - size[key](a))
        .slice(0, TOP_ITEMS)
        .map((row) => render(row, key)),
    };
  }
  return out;
}

/** A fund's quarter: which stocks it opened, added to, trimmed and sold, largest first. */
export function QuarterMoves({
  holdings,
  quarterLabel,
  active,
  onToggle,
  className,
}: {
  holdings: readonly QuarterlyHolding[];
  quarterLabel: string;
  active: MoveFilter | "all";
  onToggle: (key: MoveFilter) => void;
  className?: string;
}) {
  const value = (h: QuarterlyHolding) => parseValueString(h.value);
  const moved = (h: QuarterlyHolding) => parseValueString(h.deltaValue);
  const groups = groupMoves(
    holdings,
    {
      new: (h) => h.delta === "NEW",
      increased: (h) => h.delta !== "NEW" && h.delta !== "CLOSE" && h.deltaShares > 0,
      decreased: (h) => h.delta !== "CLOSE" && h.deltaShares < 0,
      closed: (h) => h.delta === "CLOSE",
    },
    { new: value, increased: moved, decreased: (h) => -moved(h), closed: (h) => -moved(h) },
    (h) => <TickerLink key={h.ticker} ticker={h.ticker} />,
  );
  return (
    <MovesPanel
      title="Quarter moves"
      quarterLabel={quarterLabel}
      groups={groups}
      active={active}
      onToggle={onToggle}
      layout="wrap"
      className={className}
    />
  );
}

/**
 * A stock's quarter seen from its holders: which funds opened, added to, trimmed and sold it,
 * largest first, each with the money moved and the fund's return per year from the ranking.
 */
export function HolderMoves({
  holdings,
  annualReturns,
  quarterLabel,
  active,
  onToggle,
  className,
}: {
  holdings: readonly FundTickerHolding[];
  annualReturns: ReadonlyMap<string, number | null>;
  quarterLabel: string;
  active: MoveFilter | "all";
  onToggle: (key: MoveFilter) => void;
  className?: string;
}) {
  const groups = groupMoves(
    holdings,
    HOLDER_MOVE_PICK,
    {
      new: (h) => h.value,
      increased: (h) => h.deltaValue,
      decreased: (h) => -h.deltaValue,
      closed: (h) => -h.deltaValue,
    },
    (h) => {
      const perYear = annualReturns.get(h.fund) ?? null;
      return (
        <div key={h.fund} className="flex min-w-0 items-center gap-3">
          <FundCell fundName={h.fund} className="min-w-0 flex-1" />
          <span className="flex shrink-0 flex-col items-end text-xs leading-4 tabular-nums">
            <span className={cn("font-medium", toneClass(h.deltaValue))}>
              {formatValue(h.deltaValue)}
            </span>
            {perYear !== null && (
              <span className="text-muted-foreground" title="The fund's return per year">
                {pctFrac(perYear)}/yr
              </span>
            )}
          </span>
        </div>
      );
    },
  );
  return (
    <MovesPanel
      title="Fund moves"
      quarterLabel={quarterLabel}
      groups={groups}
      active={active}
      onToggle={onToggle}
      layout="columns"
      className={className}
    />
  );
}
