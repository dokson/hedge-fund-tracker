import { useSyncExternalStore, type ReactNode } from "react";

import { TableFrame } from "@/components/ui/TableFrame";
import { cn } from "@/lib/utils";

// Tailwind's `md` is 48rem, which follows the user's font size; a px query would disagree.
const desktopQuery = "(min-width: 48rem)";

/** Subscribe to the same breakpoint used by the table layout. */
function subscribeDesktop(callback: () => void) {
  if (typeof window.matchMedia !== "function") return () => {};
  const media = window.matchMedia(desktopQuery);
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}

/** Default to desktop when media queries are unavailable, including in jsdom. */
function isDesktop() {
  return typeof window.matchMedia !== "function" || window.matchMedia(desktopQuery).matches;
}

/**
 * The table-on-desktop, cards-on-phone switch. Wide tables are unusable below `md`, so the
 * same rows render as a stacked card list there; the breakpoint lives here, not in each page.
 */
export function ResponsiveTable({
  label,
  labelledBy,
  table,
  cards,
  className,
  tableClassName,
  singleLayout = false,
}: {
  /** Names the desktop scroll region (reuse the table's aria-label). */
  label: string;
  /** Id of the table caption naming the desktop region, if present. */
  labelledBy?: string;
  table: ReactNode;
  cards: ReactNode;
  /** Classes for both renderings (spacing). */
  className?: string;
  /** Classes for the desktop table frame only, e.g. its bordered `surface`. */
  tableClassName?: string;
  /** Mount only the current viewport layout in findable, permanently mounted panels. */
  singleLayout?: boolean;
}) {
  const desktop = useSyncExternalStore(subscribeDesktop, isDesktop, () => true);
  if (singleLayout) {
    return desktop ? (
      <TableFrame label={label} labelledBy={labelledBy} className={cn(className, tableClassName)}>
        {table}
      </TableFrame>
    ) : (
      <div className={className}>{cards}</div>
    );
  }
  return (
    <>
      <div className={cn("md:hidden", className)}>{cards}</div>
      <TableFrame label={label} labelledBy={labelledBy} className={cn("hidden md:block", className, tableClassName)}>
        {table}
      </TableFrame>
    </>
  );
}
