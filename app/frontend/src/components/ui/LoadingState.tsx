import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

/** Shared "loading…" placeholder — spinner + message, centered. */
export function LoadingState({
  message,
  size = "lg",
  className,
}: {
  message: string;
  /** "lg" (default): py-12, h-5 icon. "sm": py-8, h-4 icon. */
  size?: "lg" | "sm";
  className?: string;
}) {
  const isSm = size === "sm";
  return (
    <div
      className={cn(
        "flex items-center justify-center gap-2 text-muted-foreground",
        isSm ? "py-8" : "py-12",
        className,
      )}
    >
      <Loader2 className={cn("animate-spin", isSm ? "h-4 w-4" : "h-5 w-5")} />
      {message}
    </div>
  );
}
