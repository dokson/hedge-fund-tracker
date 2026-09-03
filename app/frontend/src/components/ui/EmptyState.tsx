import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Shared "nothing here" panel. `icon` is drawn muted above the title when the
 * call site supplies one; the compact variant is a single line.
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
  /** "lg" (default): title + caption, generous padding. "sm": single compact line. */
  padding?: "lg" | "sm";
  className?: string;
}) {
  if (padding === "sm") {
    return (
      <div
        className={cn("frame px-4 py-6 text-center text-[13px] text-muted-foreground", className)}
      >
        {title}
      </div>
    );
  }
  return (
    <div className={cn("frame px-6 py-10 text-center", className)}>
      {Icon && <Icon className="mx-auto mb-2 h-5 w-5 text-muted-foreground" aria-hidden="true" />}
      <p className="text-[13px] font-medium text-foreground">{title}</p>
      {description && <p className="mt-1 text-xs text-muted-foreground">{description}</p>}
    </div>
  );
}
