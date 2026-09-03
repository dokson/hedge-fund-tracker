import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/** Tags: one neutral chip surface, the colour in the text only. */
const badgeVariants = cva("chip", {
  variants: {
    variant: {
      default: "text-primary-text",
      secondary: "text-muted-foreground",
      destructive: "text-negative",
      outline: "border border-border bg-transparent text-foreground",
    },
  },
  defaultVariants: {
    variant: "default",
  },
});

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
