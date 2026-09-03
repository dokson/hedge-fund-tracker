import { ChevronDown, ChevronUp } from "lucide-react";

import { InfoTooltip } from "@/components/ui/InfoTooltip";

type Align = "left" | "center" | "right";

export interface ColumnSort {
  active: boolean;
  direction: "asc" | "desc";
  onToggle: () => void;
}

/**
 * `<th scope="col">` label with an inline info tooltip — the shared shape
 * behind every "column name + ⓘ" header cell (Funds Config, AI Ranking, and
 * any future data table). With `sort`, the label becomes a real button and
 * the cell carries `aria-sort`, so the header is never a clickable `<th>`.
 */
export function ColumnHeader({
  label,
  tooltip,
  align = "left",
  className = "",
  sort,
}: {
  label: string;
  tooltip?: string;
  align?: Align;
  className?: string;
  sort?: ColumnSort;
}) {
  const alignClass =
    align === "center" ? "text-center" : align === "right" ? "text-right" : "text-left";
  const wrapperJustify =
    align === "center" ? "justify-center" : align === "right" ? "justify-end" : "justify-start";
  const ariaSort = sort
    ? sort.active
      ? sort.direction === "asc"
        ? "ascending"
        : "descending"
      : "none"
    : undefined;
  const SortIcon = sort?.active ? (sort.direction === "asc" ? ChevronUp : ChevronDown) : null;

  return (
    <th
      scope="col"
      aria-sort={ariaSort}
      className={`${alignClass} px-3 py-2 text-xs font-normal text-muted-foreground ${className}`}
    >
      <span className={`inline-flex items-center gap-1 ${wrapperJustify}`}>
        {sort ? (
          <button
            type="button"
            onClick={sort.onToggle}
            className="inline-flex min-h-6 items-center gap-1 transition-colors duration-[120ms] hover:text-foreground"
          >
            {label}
            {SortIcon && <SortIcon className="h-3.5 w-3.5" aria-hidden="true" />}
          </button>
        ) : (
          label
        )}
        {tooltip && <InfoTooltip text={tooltip} />}
      </span>
    </th>
  );
}
