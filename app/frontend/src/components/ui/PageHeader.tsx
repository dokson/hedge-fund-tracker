import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: ReactNode;
  /** Muted icon drawn before the title (list pages); detail pages pass `leading` instead. */
  icon?: LucideIcon;
  /** Entity slot before the title, e.g. a logo plate on a stock or fund page. */
  leading?: ReactNode;
  /** One short sentence under the title. */
  description?: ReactNode;
  /**
   * A short muted note on the title's own line, after it (a fund's manager): it uses the
   * row's spare width and wraps under the title only when the name leaves no room.
   */
  titleAside?: ReactNode;
  /** Controls aligned right of the title (star, back, primary action). */
  actions?: ReactNode;
  /** Extra lines under the description (status line, review date). */
  children?: ReactNode;
  className?: string;
}

/** The page's `<h1>` row: every page opens with the same title, icon and subtitle rhythm. */
export function PageHeader({
  title,
  icon: Icon,
  leading,
  description,
  titleAside,
  actions,
  children,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn("min-w-0 space-y-1.5", className)}>
      <div className="flex min-w-0 items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          {leading}
          <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <h1 className="page-title min-w-0">
              {Icon && <Icon aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" />}
              {title}
            </h1>
            {titleAside && <p className="text-sm text-muted-foreground">{titleAside}</p>}
          </div>
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
      {children}
    </header>
  );
}
