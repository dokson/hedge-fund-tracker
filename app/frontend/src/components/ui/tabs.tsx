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
      // The selected tab keeps the same weight: a bolder label would widen it and shift its
      // neighbours; the gold underline (a border, kept in forced colours) marks it.
      "inline-flex items-center justify-center whitespace-nowrap h-9 px-1 -mb-px text-[13px] font-normal text-muted-foreground cursor-pointer border-b-2 border-transparent transition-colors duration-[120ms] hover:text-foreground aria-selected:border-gold aria-selected:text-foreground data-[state=active]:border-gold data-[state=active]:text-foreground focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring disabled:pointer-events-none disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

type TabsContentProps = React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content> & {
  /**
   * Keep the inactive panel in the page as `hidden="until-found"`, so the browser's find in
   * page reaches its text and opens its tab (`beforematch`). Where until-found is unsupported
   * (Safari) the panel is plainly hidden, as without this prop. For panels cheap to mount.
   */
  findable?: boolean;
};

/** Until-found while the panel is inactive, visible once selected. */
function syncFindable(panel: HTMLElement) {
  if (panel.dataset.state === "inactive") panel.setAttribute("hidden", "until-found");
  else panel.removeAttribute("hidden");
}

const TabsContent = React.forwardRef<React.ElementRef<typeof TabsPrimitive.Content>, TabsContentProps>(
  ({ className, findable = false, children, ...props }, forwardedRef) => {
    const panelRef = React.useRef<HTMLDivElement | null>(null);
    const setRefs = (el: HTMLDivElement | null) => {
      panelRef.current = el;
      if (typeof forwardedRef === "function") forwardedRef(el);
      else if (forwardedRef) forwardedRef.current = el;
    };
    // A force-mounted Radix panel is never hidden by Radix, so the panel's visibility follows
    // its data-state here: until-found while inactive, nothing once selected (a click selects
    // without the browser's own reveal, which only find in page performs). Synced after every
    // render and watched too: with uncontrolled Tabs only Radix's inner content re-renders.
    React.useLayoutEffect(() => {
      if (findable && panelRef.current) syncFindable(panelRef.current);
    });
    React.useLayoutEffect(() => {
      const panel = panelRef.current;
      if (!findable || !panel) return;
      const observer = new MutationObserver(() => syncFindable(panel));
      observer.observe(panel, { attributes: true, attributeFilter: ["data-state"] });
      return () => observer.disconnect();
    }, [findable]);
    React.useEffect(() => {
      const panel = panelRef.current;
      if (!findable || !panel) return;
      // Select the panel's tab the way a pointer does: Radix triggers activate on mousedown.
      const reveal = () => {
        const trigger = document.getElementById(panel.getAttribute("aria-labelledby") ?? "");
        trigger?.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, button: 0 }));
      };
      panel.addEventListener("beforematch", reveal);
      return () => panel.removeEventListener("beforematch", reveal);
    }, [findable]);
    if (!findable) {
      return (
        <TabsPrimitive.Content ref={setRefs} className={cn("mt-3", className)} {...props}>
          {children}
        </TabsPrimitive.Content>
      );
    }
    // No margin, padding or background on a findable panel: an until-found panel keeps its
    // box, so they would show as an empty strip. They go on the wrapper inside.
    return (
      <TabsPrimitive.Content ref={setRefs} forceMount {...props}>
        <div className={cn("mt-3", className)}>{children}</div>
      </TabsPrimitive.Content>
    );
  },
);
TabsContent.displayName = TabsPrimitive.Content.displayName;

export { Tabs, TabsList, TabsTrigger, TabsContent };
