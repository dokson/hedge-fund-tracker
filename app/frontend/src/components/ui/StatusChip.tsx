import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";
import type { Tone } from "@/lib/tone";

const TONE_TEXT: Record<Tone, string> = {
  positive: "text-positive",
  negative: "text-negative",
  warning: "text-warning",
  neutral: "text-muted-foreground",
};

/** The pill for a status or tag; colour lives in the text (and a dark-mode wash, see `.chip`). */
export function StatusChip({
  tone = "neutral",
  className,
  children,
  ...rest
}: Omit<HTMLAttributes<HTMLSpanElement>, "children"> & {
  tone?: Tone;
  children: ReactNode;
}) {
  return (
    <span {...rest} className={cn("chip", TONE_TEXT[tone], className)}>
      {children}
    </span>
  );
}
