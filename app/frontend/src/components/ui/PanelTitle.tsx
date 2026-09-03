import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface PanelTitleProps {
  children: ReactNode;
  /**
   * 2 by default. Pass 3 only when the panel is nested under a section that
   * already owns an `<h2>`, so the outline never skips a level.
   */
  level?: 2 | 3;
  id?: string;
  className?: string;
}

/**
 * The title inside a `.frame-title` header row. The row itself stays a plain
 * flex `<div>` (title left, controls right); only the text becomes a heading,
 * so panels appear in the screen-reader heading map without any visual change.
 */
export function PanelTitle({ children, level = 2, id, className }: PanelTitleProps) {
  const Heading = level === 3 ? "h3" : "h2";
  return (
    <Heading id={id} className={cn("min-w-0", className)}>
      {children}
    </Heading>
  );
}
