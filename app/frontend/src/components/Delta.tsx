import { TrendingUp, TrendingDown, Minus } from "lucide-react";

import { formatValue, formatPct } from "@/lib/dataService";

interface DeltaProps {
  value: number;
  /** "currency" → $1.2M ; "percent" → 12.3% */
  mode: "currency" | "percent";
  /**
   * Custom formatter override (e.g. when the caller already has a string
   * like "+10.5%" and just wants the icon + colour treatment).
   */
  format?: (v: number) => string;
  /** Smaller variant for in-cell secondary rows. */
  size?: "sm" | "md";
  className?: string;
}

/**
 * Uniform delta cell across all tables and headers. Positive values get the
 * positive token + TrendingUp; negative values get the negative token +
 * TrendingDown; exact zero is muted with a flat dash. NEW / CLOSE special
 * states are not handled here — those are categorical, not numeric, and
 * keep their existing badge treatment.
 */
export function Delta({ value, mode, format, size = "md", className = "" }: DeltaProps) {
  const isZero = value === 0;
  const isPositive = value > 0;
  const isInfinity = !isFinite(value);
  const colorClass = isZero
    ? "text-muted-foreground"
    : isPositive || isInfinity
      ? "delta-positive"
      : "delta-negative";
  const Icon = isZero ? Minus : isPositive || isInfinity ? TrendingUp : TrendingDown;
  const iconSize = size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5";
  const textSize = size === "sm" ? "text-[11px]" : "text-xs";

  let display: string;
  if (format) {
    display = format(value);
  } else if (isZero) {
    // A literal zero is "no activity", not a +0.0% move — label it like the
    // categorical NO CHANGE state the filing tables use.
    display = "NO CHANGE";
  } else if (mode === "currency") {
    display = `${isPositive && !isInfinity ? "+" : ""}${formatValue(value)}`;
  } else {
    display = formatPct(value, true);
  }

  return (
    <span
      className={`inline-flex items-center gap-1 font-mono ${textSize} ${colorClass} ${className}`}
    >
      {!isZero && <Icon className={iconSize} aria-hidden="true" />}
      {display}
    </span>
  );
}
