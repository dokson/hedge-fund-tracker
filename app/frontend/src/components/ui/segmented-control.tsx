import * as React from "react";

import { cn } from "@/lib/utils";

export interface SegmentedOption<T extends string = string> {
  value: T;
  label: React.ReactNode;
  /** Tooltip + accessible name — required when `label` is icon-only. */
  title?: string;
}

interface SegmentedControlProps<T extends string> extends Omit<
  React.HTMLAttributes<HTMLDivElement>,
  "onChange"
> {
  value: T;
  onValueChange: (value: T) => void;
  options: readonly SegmentedOption<T>[];
  size?: "sm" | "default";
}

/** A track of segments; the checked one is lifted onto the panel colour. */
export function SegmentedControl<T extends string>({
  value,
  onValueChange,
  options,
  size = "default",
  className,
  ...props
}: SegmentedControlProps<T>) {
  return (
    <div
      role="radiogroup"
      className={cn("inline-flex items-stretch rounded-md bg-muted p-0.5", className)}
      {...props}
    >
      {options.map((opt) => {
        const isActive = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={isActive}
            aria-label={opt.title}
            title={opt.title}
            onClick={() => onValueChange(opt.value)}
            className={cn(
              "rounded-sm font-medium transition-colors duration-[120ms] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
              size === "sm" ? "px-2 h-6 text-xs" : "px-3 h-8 text-[13px]",
              isActive ? "bg-card text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
