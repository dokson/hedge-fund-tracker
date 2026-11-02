import type { ReactNode } from "react";

import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { cn } from "@/lib/utils";

/** Hairline-divided grid of `Stat` cells; pass the column classes for each breakpoint. */
export function StatGrid({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={cn(
        "grid gap-px overflow-hidden rounded-md border border-border bg-border",
        className,
      )}
    >
      {children}
    </div>
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
  className?: string;
}

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
  className,
}: StatProps) {
  const body = (
    <>
      <span
        className={cn(
          "metric-label inline-flex items-center gap-1",
          active && "!text-primary-foreground",
        )}
      >
        {label}
        {info && <InfoTooltip text={info} className={active ? "!text-primary-foreground" : undefined} />}
      </span>
      <span
        className={cn(
          "tabular-nums",
          size === "lg" ? "metric-value" : "text-lg font-medium leading-6",
          active && "!text-primary-foreground",
          valueClassName,
        )}
      >
        {value}
      </span>
      {hint && (
        <span className={cn("text-xs text-muted-foreground", active && "!text-primary-foreground")}>
          {hint}
        </span>
      )}
    </>
  );
  const cell = "kpi-card min-w-0 items-start text-left";
  if (!onClick) return <div className={cn(cell, className)}>{body}</div>;
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        cell,
        "transition-colors",
        active ? "!bg-primary text-primary-foreground" : "hover:!bg-muted",
        className,
      )}
    >
      {body}
    </button>
  );
}
