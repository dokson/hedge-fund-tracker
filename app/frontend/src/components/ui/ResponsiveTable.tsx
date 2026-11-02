import type { ReactNode } from "react";

import { TableFrame } from "@/components/ui/TableFrame";
import { cn } from "@/lib/utils";

/**
 * The table-on-desktop, cards-on-phone switch. Wide tables are unusable below `md`, so the
 * same rows render as a stacked card list there; the breakpoint lives here, not in each page.
 */
export function ResponsiveTable({
  label,
  table,
  cards,
  className,
  tableClassName,
}: {
  /** Names the desktop scroll region (reuse the table's aria-label). */
  label: string;
  table: ReactNode;
  cards: ReactNode;
  /** Classes for both renderings (spacing). */
  className?: string;
  /** Classes for the desktop table frame only, e.g. its bordered `surface`. */
  tableClassName?: string;
}) {
  return (
    <>
      <div className={cn("md:hidden", className)}>{cards}</div>
      <TableFrame label={label} className={cn("hidden md:block", className, tableClassName)}>
        {table}
      </TableFrame>
    </>
  );
}
