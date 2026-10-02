import type { ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Renders a query's error in place of its content, so a failed load reads as
 * an error rather than as an empty dataset.
 */
export function QueryState({
  isError,
  error,
  title = "Could not load data",
  className,
  children,
}: {
  isError: boolean;
  error: unknown;
  title?: string;
  className?: string;
  children?: ReactNode;
}) {
  if (!isError) return <>{children}</>;
  const detail = error instanceof Error ? error.message : undefined;
  return (
    <div role="alert" className={cn("frame px-6 py-10 text-center", className)}>
      <AlertTriangle className="mx-auto mb-2 h-5 w-5 text-destructive" aria-hidden="true" />
      <p className="text-[13px] font-medium text-foreground">{title}</p>
      {detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
    </div>
  );
}
