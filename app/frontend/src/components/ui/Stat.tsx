import type { ReactNode } from "react";

import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { cn } from "@/lib/utils";

/**
 * Hairline-divided grid of `Stat` cells; pass the column classes for each breakpoint. A grid
 * of read-only figures is a definition list (each cell a `dt` label with its `dd` value and
 * note), so assistive tech pairs every value with its label. `toggles` makes it a plain grid
 * for filter cells, whose buttons a `dl` may not hold.
 */
export function StatGrid({
  className,
  children,
  toggles = false,
}: {
  className?: string;
  children: ReactNode;
  toggles?: boolean;
}) {
  const Tag = toggles ? "div" : "dl";
  return (
    <Tag
      className={cn(
        "grid gap-px overflow-hidden rounded-md border border-border bg-border",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

interface StatProps {
  label: ReactNode;
  value: ReactNode;
  /** Tooltip text next to the label. */
  info?: string;
  /** Small line under the value. */
  hint?: ReactNode;
  /** Tone class for the value, e.g. from `toneClass`. */
  valueClassName?: string;
  /** "lg" for headline counters, "md" for dense KPI rows. */
  size?: "md" | "lg";
  /** Makes the cell a toggle button (filter cells). */
  onClick?: () => void;
  active?: boolean;
  /**
   * The meaning of the count: a selected toggle takes this tone (a wash and a ring of it,
   * the value staying in it) instead of the primary fill, so a selected "Decreased" still reads red.
   */
  tone?: "positive" | "negative";
  className?: string;
}

// Opaque: a translucent wash composites over the grid's hairline ground, not the card, and
// took the 12px label to 3.8:1. Mixed over --card, every label and value stays above 4.5:1
// in both themes (worst: light positive value, 4.54).
const ACTIVE_TONE = {
  positive:
    "!bg-[color-mix(in_srgb,hsl(var(--positive))_14%,hsl(var(--card)))] ring-2 ring-inset ring-[hsl(var(--positive))]",
  negative:
    "!bg-[color-mix(in_srgb,hsl(var(--negative))_14%,hsl(var(--card)))] ring-2 ring-inset ring-[hsl(var(--negative))]",
} as const;

/** One label-over-value cell: the shared shape of every KPI, counter and filter cell. */
export function Stat({
  label,
  value,
  info,
  hint,
  valueClassName,
  size = "md",
  onClick,
  active = false,
  tone,
  className,
}: StatProps) {
  // A toned selection keeps the page's text colours; the primary fill needs its own ink.
  const filled = active && !tone;
  const body = (
    <>
      <span
        className={cn(
          "metric-label inline-flex items-center gap-1",
          filled && "!text-primary-foreground",
        )}
      >
        {label}
        {onClick && active && <span aria-hidden="true">✓</span>}
        {info && <InfoTooltip
            text={info}
            label={typeof label === "string" ? label : undefined}
            className={filled ? "!text-primary-foreground" : undefined}
          />}
      </span>
      <span
        className={cn(
          "tabular-nums",
          size === "lg" ? "metric-value" : "text-lg font-medium leading-6",
          filled && "!text-primary-foreground",
          valueClassName,
        )}
      >
        {value}
      </span>
      {hint && (
        <span className={cn("text-xs text-muted-foreground", filled && "!text-primary-foreground")}>
          {hint}
        </span>
      )}
    </>
  );
  const cell = "kpi-card min-w-0 items-start text-left";
  if (!onClick) {
    // A read-only cell inside the grid's `dl`: the label is the term, value and note its
    // descriptions (a div group of dt/dd is valid inside a dl).
    return (
      <div className={cn(cell, className)}>
        <dt className="metric-label inline-flex items-center gap-1">
          {label}
          {info && (
            <InfoTooltip text={info} label={typeof label === "string" ? label : undefined} />
          )}
        </dt>
        <dd
          className={cn(
            "tabular-nums",
            size === "lg" ? "metric-value" : "text-lg font-medium leading-6",
            valueClassName,
          )}
        >
          {value}
        </dd>
        {hint && <dd className="text-xs text-muted-foreground">{hint}</dd>}
      </div>
    );
  }
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        cell,
        // The grid clips anything drawn outside a cell, so the focus ring sits inside it.
        "transition-colors focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-foreground",
        "forced-colors:aria-pressed:border-2 forced-colors:aria-pressed:border-[Highlight]",
        active
          ? tone
            ? ACTIVE_TONE[tone]
            : "!bg-primary text-primary-foreground"
          : "hover:!bg-muted",
        className,
      )}
    >
      {body}
    </button>
  );
}
