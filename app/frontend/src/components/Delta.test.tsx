/**
 * Tests for the uniform <Delta> cell. The component is consumed across every
 * table that renders a positive/negative numeric change (Dashboard latest
 * filings, QuarterlyTrends, FundPortfolio holdings), so its colour & icon
 * contract is load-bearing for visual consistency.
 */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { Delta } from "./Delta";

describe("Delta", () => {
  it("renders an up-arrow + positive token for positive percent values", () => {
    const { container } = render(<Delta value={12.34} mode="percent" />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("delta-positive");
    expect(root.textContent).toContain("+12.3%");
  });

  it("renders a down-arrow + negative token for negative percent values", () => {
    const { container } = render(<Delta value={-5.6} mode="percent" />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("delta-negative");
    expect(root.textContent).toContain("-5.6%");
  });

  it("renders a muted dash for exactly-zero values", () => {
    const { container } = render(<Delta value={0} mode="percent" />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("text-muted-foreground");
  });

  it("formats currency values with sign + compact suffix", () => {
    const { container } = render(<Delta value={12_500_000} mode="currency" />);
    expect(container.textContent).toContain("+$12.50M");
  });

  it("treats Infinity (all-new positions) as positive", () => {
    const { container } = render(<Delta value={Infinity} mode="percent" />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("delta-positive");
    expect(root.textContent).toContain("NEW");
  });

  it("honours a custom formatter when provided", () => {
    const { container } = render(<Delta value={42} mode="percent" format={(v) => `${v} units`} />);
    expect(container.textContent).toContain("42 units");
  });
});
