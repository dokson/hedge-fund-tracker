import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const PLATE_SIZE = {
  sm: "h-8 w-8",
  md: "h-10 w-10",
  lg: "h-12 w-12",
} as const;

/** Square, bordered slot that seats a `CompanyLogo` or `FundLogo` in rows and headers. */
export function LogoPlate({
  size = "sm",
  className,
  children,
}: {
  size?: keyof typeof PLATE_SIZE;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-sm border border-border bg-card",
        PLATE_SIZE[size],
        className,
      )}
    >
      {children}
    </span>
  );
}
