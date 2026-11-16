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
  // Radiogroup contract: one tab stop (the checked radio), arrows move and select.
  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const step =
      event.key === "ArrowRight" || event.key === "ArrowDown"
        ? 1
        : event.key === "ArrowLeft" || event.key === "ArrowUp"
          ? -1
          : 0;
    if (step === 0) return;
    event.preventDefault();
    const index = options.findIndex((opt) => opt.value === value);
    const next = options[(index + step + options.length) % options.length];
    onValueChange(next.value);
    const radios = event.currentTarget.querySelectorAll<HTMLElement>('[role="radio"]');
    radios[options.indexOf(next)]?.focus();
  };

  const hasActive = options.some((opt) => opt.value === value);

  return (
    <div
      role="radiogroup"
      onKeyDown={onKeyDown}
      className={cn("inline-flex items-stretch rounded-lg border border-border bg-muted p-0.5", className)}
      {...props}
    >
      {options.map((opt, i) => {
        const isActive = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={isActive}
            tabIndex={isActive || (!hasActive && i === 0) ? 0 : -1}
            aria-label={opt.title}
            title={opt.title}
            onClick={() => onValueChange(opt.value)}
            className={cn(
              "rounded-md font-medium transition-colors duration-[120ms] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
              size === "sm"
                ? "px-3 h-9 text-[13px] md:px-2 md:h-6 md:text-xs"
                : "px-3 h-10 text-sm md:h-8 md:text-[13px]",
              isActive
                ? "bg-card text-foreground shadow-sm forced-colors:bg-[Highlight] forced-colors:text-[HighlightText]"
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
