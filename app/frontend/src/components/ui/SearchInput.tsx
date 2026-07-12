import * as React from "react";
import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface SearchInputProps extends Omit<
  React.ComponentProps<typeof Input>,
  "placeholder" | "aria-label" | "type" | "size"
> {
  /** Used verbatim as the accessible name, and with a trailing ellipsis as the placeholder — a
   * single source of truth so the two can't drift apart. */
  label: string;
  /** Classes for the positioning wrapper (e.g. width), as opposed to `className` for the input itself. */
  wrapperClassName?: string;
  size?: "sm" | "default";
}

export function SearchInput({
  label,
  wrapperClassName,
  size = "default",
  className,
  ...props
}: SearchInputProps) {
  const isSm = size === "sm";
  return (
    <div className={cn("relative", wrapperClassName)}>
      <Search
        className={cn(
          "absolute top-1/2 -translate-y-1/2 text-muted-foreground",
          isSm ? "left-2.5 h-3.5 w-3.5" : "left-3 h-4 w-4",
        )}
      />
      <Input
        placeholder={`${label}…`}
        aria-label={label}
        className={cn(isSm ? "pl-8" : "pl-9", "bg-card border-border", className)}
        {...props}
      />
    </div>
  );
}
