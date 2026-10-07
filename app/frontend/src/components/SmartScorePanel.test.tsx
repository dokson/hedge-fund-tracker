import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import { SmartScorePanel } from "./SmartScorePanel";
import { FAQ_SECTIONS } from "@/lib/faqContent";
import type { SmartScoreView } from "@/lib/smartScore";

const score: SmartScoreView = {
  smartScore: 8.6,
  breadth: 50.6,
  momentum: 78.1,
  conviction: 89.3,
};

const renderPanel = (props: { score: SmartScoreView | undefined; quarterLabel?: string }) =>
  render(
    <MemoryRouter>
      <SmartScorePanel {...props} />
    </MemoryRouter>,
  );

describe("SmartScorePanel", () => {
  it("renders nothing without a score", () => {
    const { container } = renderPanel({ score: undefined });
    expect(container.firstElementChild).toBeNull();
  });

  it("renders the composite, the three components and the quarter label", () => {
    const { container } = renderPanel({ score, quarterLabel: "2026Q2" });
    expect(container.textContent).toContain("8.6");
    expect(container.textContent).toContain("Breadth");
    expect(container.textContent).toContain("Momentum");
    expect(container.textContent).toContain("Conviction");
    expect(container.textContent).toContain("2026 Q2");
  });

  it("links to the FAQ entry that defines the score, and that entry exists", () => {
    renderPanel({ score, quarterLabel: "2026Q2" });

    const href = screen.getByRole("link", { name: "How is this calculated?" }).getAttribute("href");
    const id = href?.split("#")[1];
    const faqIds = FAQ_SECTIONS.flatMap((s) => s.items).map((item) => item.id);

    expect(href?.startsWith("/learn#")).toBe(true);
    expect(faqIds).toContain(id);
  });
});
