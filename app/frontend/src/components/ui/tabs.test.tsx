import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

const ACTIVE = ["aria-selected:border-primary", "aria-selected:text-foreground"];

describe("TabsTrigger", () => {
  it("marks the active trigger and only the active trigger", () => {
    render(
      <Tabs value="one">
        <TabsList>
          <TabsTrigger value="one">One</TabsTrigger>
          <TabsTrigger value="two">Two</TabsTrigger>
        </TabsList>
        <TabsContent value="one">first</TabsContent>
      </Tabs>,
    );

    const active = screen.getByRole("tab", { name: "One" });
    const inactive = screen.getByRole("tab", { name: "Two" });

    expect(active.getAttribute("aria-selected")).toBe("true");
    expect(inactive.getAttribute("aria-selected")).toBe("false");
    // Inactive is muted and unemphasised; the active styling is variant-gated.
    expect(inactive.className).toContain("text-muted-foreground");
    expect(inactive.className).toContain("font-normal");
    for (const cls of ACTIVE) expect(active.className).toContain(cls);
  });

  it("stays distinguishable when wrapped in a TooltipTrigger", () => {
    // Regression: TooltipTrigger asChild pushes its own data-state ("closed")
    // into the Tabs trigger, which Radix spreads over its own data-state.
    render(
      <TooltipProvider>
        <Tabs value="one">
          <TabsList>
            <Tooltip>
              <TooltipTrigger asChild>
                <TabsTrigger value="one">One</TabsTrigger>
              </TooltipTrigger>
              <TooltipContent>first</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <TabsTrigger value="two">Two</TabsTrigger>
              </TooltipTrigger>
              <TooltipContent>second</TooltipContent>
            </Tooltip>
          </TabsList>
        </Tabs>
      </TooltipProvider>,
    );

    const active = screen.getByRole("tab", { name: "One" });
    const inactive = screen.getByRole("tab", { name: "Two" });

    // data-state is clobbered by the tooltip, so aria-selected is the signal.
    expect(active.getAttribute("aria-selected")).toBe("true");
    expect(inactive.getAttribute("aria-selected")).toBe("false");
    for (const cls of ACTIVE) expect(active.className).toContain(cls);
  });
});
