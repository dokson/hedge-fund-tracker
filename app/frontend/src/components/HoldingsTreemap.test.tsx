import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HoldingsTreemap } from "./HoldingsTreemap";

const data = [
  {
    name: "AAA",
    company: "Alpha Company With Its Full Research Name",
    value: 99,
    deltaPct: 25,
    delta: "INCREASE",
  },
  { name: "TINY", company: "Tiny Company", value: 1, deltaPct: -10, delta: "DECREASE" },
];

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      constructor(private callback: ResizeObserverCallback) {}
      observe(target: Element) {
        this.callback(
          [{ target, contentRect: { width: 300, height: 100 } } as ResizeObserverEntry],
          this as unknown as ResizeObserver,
        );
      }
      disconnect() {}
      unobserve() {}
    },
  );
});

describe("HoldingsTreemap", () => {
  it("leaves microcells unlabelled while keeping their full information keyboard accessible", () => {
    const onClickTicker = vi.fn<(ticker: string) => void>();
    render(
      <HoldingsTreemap data={data} height={100} displayMode="pct" onClickTicker={onClickTicker} />,
    );
    const tile = screen.getByRole("button", { name: "TINY" });
    expect(tile.textContent).toBe("");
    fireEvent.focus(tile);
    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.textContent).toContain("Tiny Company");
    expect(tooltip.textContent).toContain("1.0%");
    expect(tile.getAttribute("aria-describedby")).toBe(tooltip.id);
    fireEvent.click(tile);
    expect(onClickTicker).toHaveBeenCalledWith("TINY");
    fireEvent.keyDown(tile, { key: "Escape" });
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("shows the complete company name and monetary value on focus, then closes on blur", () => {
    render(
      <HoldingsTreemap
        data={data}
        height={100}
        onClickTicker={vi.fn<(ticker: string) => void>()}
        activeName="TINY"
      />,
    );
    const tile = screen.getByRole("button", { name: "AAA" });
    fireEvent.focus(tile);
    expect(screen.getByRole("tooltip").textContent).toContain(data[0].company);
    expect(screen.getByRole("tooltip").textContent).toContain("$99");
    expect(tile.getAttribute("aria-pressed")).toBe("false");
    fireEvent.blur(tile);
    expect(screen.queryByRole("tooltip")).toBeNull();
  });
});
