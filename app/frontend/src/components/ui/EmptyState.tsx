import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Shared "nothing here yet" placeholder — a `.surface` box with an optional
 * icon, a title, and an optional caption. Used for empty tabs/lists/panels
 * across the app instead of hand-rolling the same three elements per page.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  padding = "lg",
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  /** "lg" (default): icon + title + caption, generous padding. "sm": single compact line. */
  padding?: "lg" | "sm";
  className?: string;
}) {
  if (padding === "sm") {
    return (
      <div className={cn("surface p-8 text-center text-sm text-muted-foreground", className)}>
        {title}
      </div>
    );
  }
  return (
    <div className={cn("surface p-12 text-center", className)}>
      {Icon && <Icon className="h-8 w-8 mx-auto icon-faint mb-3" />}
      <p className="text-muted-foreground">{title}</p>
      {description && <p className="text-xs text-faint mt-1">{description}</p>}
    </div>
  );
}
