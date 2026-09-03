import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";

import { cn } from "@/lib/utils";

const Tabs = TabsPrimitive.Root;

/** Underline tabs: the active one carries a 2px primary rule. */
const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn("inline-flex items-stretch gap-4 border-b border-border", className)}
    {...props}
  />
));
TabsList.displayName = TabsPrimitive.List.displayName;

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      // Keyed off BOTH aria-selected and data-state. A `<TooltipTrigger asChild>`
      // wrapper passes its own data-state ("closed") down, and Radix's Tabs trigger
      // spreads incoming props AFTER its own data-state, so data-[state=active]
      // silently never matches. aria-selected is not clobbered that way.
      "inline-flex items-center justify-center whitespace-nowrap h-9 px-1 -mb-px text-[13px] font-normal text-muted-foreground cursor-pointer border-b-2 border-transparent transition-colors duration-[120ms] hover:text-foreground aria-selected:border-primary aria-selected:text-foreground aria-selected:font-medium data-[state=active]:border-primary data-[state=active]:text-foreground data-[state=active]:font-medium focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring disabled:pointer-events-none disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn("mt-3 focus-visible:outline-none", className)}
    {...props}
  />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

export { Tabs, TabsList, TabsTrigger, TabsContent };
