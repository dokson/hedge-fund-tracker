import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

import { InfoTooltip } from "./InfoTooltip";

describe("InfoTooltip", () => {
  it("is a real control: reachable by keyboard, and focusing it shows the hint", async () => {
    render(
      <TooltipProvider>
        <InfoTooltip text="Percentile rank of how many funds hold the stock" />
      </TooltipProvider>,
    );

    const trigger = screen.getByRole("button", { name: "More information" });
    trigger.focus();

    const tip = await screen.findByRole("tooltip");
    expect(tip.textContent).toContain("Percentile rank of how many funds hold the stock");
  });
});
