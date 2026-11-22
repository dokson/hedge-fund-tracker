import { SortArrow } from "@/components/ui/SortArrow";
import type { SortDir } from "@/hooks/useSortState";
import { announce, sortMessage } from "@/lib/announce";
import { cn } from "@/lib/utils";

/**
 * The sort control of a table's card view (below `md`): the cards have no column headers,
 * so each sortable column becomes a button here, bound to the same sort state as the table.
 * Pressing the active one flips the direction, another one starts descending; the result is
 * announced through the app's status region, like a table header.
 */
export function CardSortBar<K extends string>({
  options,
  sortKey,
  sortDir,
  onToggle,
  className,
}: {
  options: readonly { key: K; label: string }[];
  sortKey: K;
  sortDir: SortDir;
  onToggle: (key: K) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-2 overflow-x-auto", className)}>
      <span className="control-label shrink-0">Sort</span>
      {options.map(({ key, label }) => {
        const active = sortKey === key;
        return (
          <button
            key={key}
            type="button"
            aria-pressed={active}
            onClick={() => {
              onToggle(key);
              announce(sortMessage(label, active && sortDir === "desc" ? "asc" : "desc"));
            }}
            className={cn(
              "inline-flex h-9 shrink-0 items-center gap-1 rounded-md border px-3 text-xs transition-colors",
              active
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card text-muted-foreground",
            )}
          >
            {label}
            <SortArrow active={active} direction={sortDir} />
          </button>
        );
      })}
    </div>
  );
}
