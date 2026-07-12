import { InfoTooltip } from "@/components/ui/InfoTooltip";

type Align = "left" | "center" | "right";

/**
 * `<th>` label with an inline info tooltip — the shared shape behind every
 * "column name + ⓘ" header cell (Funds Config, AI Ranking, and any future
 * data table), so the tooltip wiring and alignment logic live in one place.
 */
export function ColumnHeader({
  label,
  tooltip,
  align = "left",
  className = "",
}: {
  label: string;
  tooltip: string;
  align?: Align;
  className?: string;
}) {
  const alignClass =
    align === "center" ? "text-center" : align === "right" ? "text-right" : "text-left";
  const wrapperJustify =
    align === "center" ? "justify-center" : align === "right" ? "justify-end" : "justify-start";
  return (
    <th className={`${alignClass} p-3 font-medium ${className}`}>
      <span className={`inline-flex items-center gap-1 ${wrapperJustify}`}>
        {label}
        <InfoTooltip text={tooltip} />
      </span>
    </th>
  );
}
