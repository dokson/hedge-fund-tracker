import { describe, expect, it } from "vitest";

import { treemapLabel } from "./treemapLabel";

describe("treemapLabel", () => {
  it("keeps a short name on one line at full size", () => {
    expect(treemapLabel("SNDK", 200, 80, true)).toEqual({ lines: ["SNDK"], fontSize: 14 });
  });

  it("wraps a long multi-word name onto two lines instead of dropping it", () => {
    const label = treemapLabel("Communication Services", 110, 70, true);
    expect(label?.lines).toEqual(["Communication", "Services"]);
    expect(label?.fontSize).toBeGreaterThanOrEqual(11);
  });

  // The split with the shortest longest line allows the largest font.
  it("balances the split across the words", () => {
    expect(treemapLabel("Consumer Cyclical Goods", 130, 80, false)?.lines).toEqual([
      "Consumer",
      "Cyclical Goods",
    ]);
  });

  it("drops names that cannot fit in full instead of showing fragments", () => {
    expect(treemapLabel("Communication Services", 60, 70, true)).toBeNull();
    expect(treemapLabel("SUPERCALIFRAGILISTIC", 50, 80, false)).toBeNull();
  });

  it("requires a readable minimum tile size", () => {
    expect(treemapLabel("A", 43, 70, false)).toBeNull();
    expect(treemapLabel("A", 44, 23, false)).toBeNull();
    expect(treemapLabel("A", 44, 24, false)?.lines).toEqual(["A"]);
    expect(treemapLabel("A", 44, 39, true)).toBeNull();
    expect(treemapLabel("A", 44, 40, true)?.lines).toEqual(["A"]);
  });
});
