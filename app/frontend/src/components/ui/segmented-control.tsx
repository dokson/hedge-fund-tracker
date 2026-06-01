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
      className={cn("inline-flex rounded-lg border border-border bg-card p-0.5", className)}
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
            onClick={() => onValueChange(opt.value)}
            className={cn(
              "rounded-md font-medium transition-colors",
              size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm",
              isActive
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
