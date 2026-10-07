import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

/** Shared "loading…" line: a spinner and the message, centred. */
export function LoadingState({
  message,
  size = "lg",
  className,
}: {
  message: string;
  /** "lg" (default): py-12. "sm": py-8. */
  size?: "lg" | "sm";
  className?: string;
}) {
  return (
    <div
      role="status"
      style={{ animationDelay: "300ms", animationFillMode: "backwards" }}
      className={cn(
        "flex animate-in fade-in-0 items-center justify-center gap-2 text-[13px] text-muted-foreground",
        size === "sm" ? "py-8" : "py-12",
        className,
      )}
    >
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
