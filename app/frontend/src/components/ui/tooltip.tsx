import * as React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";

import { cn } from "@/lib/utils";
import { usePortalContainer } from "@/lib/portalContainer";

const TooltipProvider = TooltipPrimitive.Provider;

const Tooltip = TooltipPrimitive.Root;

const TooltipTrigger = TooltipPrimitive.Trigger;

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, collisionPadding = 8, ...props }, ref) => {
  // Inside a native modal the tooltip must live in the dialog: outside it is below the top
  // layer and would never show.
  const container = usePortalContainer();
  return (
    // In a portal: a tooltip inside a scrolling table or a clipped panel would be cut by it.
    <TooltipPrimitive.Portal container={container}>
      <TooltipPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        collisionPadding={collisionPadding}
        className={cn(
          "z-50 overflow-hidden rounded-lg border border-border bg-popover px-3 py-1.5 text-xs text-popover-foreground shadow-md",
          className,
        )}
        {...props}
      />
    </TooltipPrimitive.Portal>
  );
});
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider };
