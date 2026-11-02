import { useId, type ReactNode } from "react";

import { PanelTitle } from "@/components/ui/PanelTitle";
import { cn } from "@/lib/utils";

interface PanelProps {
  /** Header row title; omit for an untitled surface. */
  title?: ReactNode;
  /** Right side of the header row: a hint, a count, or compact controls. */
  aside?: ReactNode;
  /** Heading level of the title (3 when nested under a section that owns an `<h2>`). */
  level?: 2 | 3;
  /** Adds space under the header for bodies without their own top padding. */
  spaced?: boolean;
  /** Explicit heading id when something else references it. */
  titleId?: string;
  className?: string;
  children?: ReactNode;
  /** Extra classes for the header row (e.g. letting a long title or actions wrap). */
  headerClassName?: string;
}

/**
 * The bordered card every panel uses: `.frame` surface, an optional `.frame-title` header
 * row whose title is a real heading, and the section labelled by that heading.
 */
export function Panel({
  title,
  aside,
  level = 2,
  spaced = false,
  titleId,
  className,
  headerClassName,
  children,
}: PanelProps) {
  const autoId = useId();
  const headingId = titleId ?? autoId;
  return (
    <section
      aria-labelledby={title ? headingId : undefined}
      className={cn("frame overflow-hidden", className)}
    >
      {title && (
        <div className={cn("frame-title", spaced && "frame-title--spaced", headerClassName)}>
          <PanelTitle id={headingId} level={level}>
            {title}
          </PanelTitle>
          {aside && (
            <div className="flex shrink-0 items-center gap-2 text-xs font-normal text-muted-foreground">
              {aside}
            </div>
          )}
        </div>
      )}
      {children}
    </section>
  );
}
