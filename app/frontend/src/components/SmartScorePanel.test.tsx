import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { SmartScorePanel } from "./SmartScorePanel";
import type { SmartScoreView } from "@/lib/smartScore";

const score: SmartScoreView = {
  smartScore: 8.6,
  breadth: 50.6,
  momentum: 78.1,
  conviction: 89.3,
};

describe("SmartScorePanel", () => {
  it("renders nothing without a score", () => {
    const { container } = render(<SmartScorePanel score={undefined} />);
    expect(container.firstElementChild).toBeNull();
  });

  it("renders the composite, the three components and the quarter label", () => {
    const { container } = render(<SmartScorePanel score={score} quarterLabel="2026Q2" />);
    expect(container.textContent).toContain("8.6");
    expect(container.textContent).toContain("Breadth");
    expect(container.textContent).toContain("Momentum");
    expect(container.textContent).toContain("Conviction");
    expect(container.textContent).toContain("2026 Q2");
  });
});
