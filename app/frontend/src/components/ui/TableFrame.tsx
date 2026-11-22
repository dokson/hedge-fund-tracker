import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface TableFrameProps {
  /**
   * Names the scroll region. Reuse the wrapped table's caption or aria-label
   * so the region and the table announce as the same thing.
   */
  label: string;
  /** When a visible or visually hidden caption exists, use it to name the region. */
  labelledBy?: string;
  className?: string;
  children: ReactNode;
}

/**
 * Horizontal scroll container for a data table. A bare `overflow-x-auto` div
 * becomes a scroll container at narrow widths that a keyboard-only user cannot
 * reach or pan (SC 2.1.1); making it a named, focusable region fixes that and
 * gives the arrow keys something to act on.
 */
export function TableFrame({ label, labelledBy, className, children }: TableFrameProps) {
  return (
    <div
      role="region"
      aria-label={labelledBy ? undefined : label}
      aria-labelledby={labelledBy}
      // A scrollable region must be focusable to be keyboard-operable (SC
      // 2.1.1), which is what jsx-a11y/no-noninteractive-tabindex would flag.
      tabIndex={0}
      className={cn("overflow-x-auto", className)}
    >
      {children}
    </div>
  );
}
