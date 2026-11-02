import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import { SmartScorePanel } from "./SmartScorePanel";
import { FAQ_SECTIONS } from "@/lib/faqContent";
import type { SmartScoreView } from "@/lib/smartScore";
import { TooltipProvider } from "@/components/ui/tooltip";

const score: SmartScoreView = {
  smartScore: 8.6,
  breadth: 50.6,
  momentum: 78.1,
  conviction: 89.3,
};

const renderPanel = (props: { score: SmartScoreView | undefined; quarterLabel?: string }) =>
  render(
    <MemoryRouter>
      <TooltipProvider>
        <SmartScorePanel {...props} />
      </TooltipProvider>
    </MemoryRouter>,
  );

describe("SmartScorePanel", () => {
  it("renders nothing without a score", () => {
    const { container } = renderPanel({ score: undefined });
    expect(container.firstElementChild).toBeNull();
  });

  it("links to the FAQ entry that defines the score, and that entry exists", () => {
    renderPanel({ score, quarterLabel: "2026Q2" });

    const href = screen.getByRole("link", { name: "Method FAQ" }).getAttribute("href");
    const id = href?.split("#")[1];
    const faqIds = FAQ_SECTIONS.flatMap((s) => s.items).map((item) => item.id);

    expect(href?.startsWith("/learn#")).toBe(true);
    expect(faqIds).toContain(id);
  });

  it("shows the component values with their meanings and preserves unavailable values", () => {
    renderPanel({ score: { ...score, momentum: null } });

    expect(screen.getByRole("heading", { name: "Smart Score" })).toBeTruthy();
    expect(screen.getByText("51")).toBeTruthy();
    expect(screen.getByText("—")).toBeTruthy();
    expect(screen.getByText("89")).toBeTruthy();
    expect(screen.getByText("Net fund buyers, not price momentum")).toBeTruthy();
    expect(screen.getByRole("button", { name: "More information" })).toBeTruthy();
  });
});
