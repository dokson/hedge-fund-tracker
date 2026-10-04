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
    expect(treemapLabel("Consumer Cyclical Goods", 100, 80, false)?.lines).toEqual([
      "Consumer",
      "Cyclical Goods",
    ]);
  });

  it("truncates with an ellipsis before giving up", () => {
    expect(treemapLabel("Communication Services", 60, 70, true)).toEqual({
      lines: ["Communi…"],
      fontSize: 11,
    });
    expect(treemapLabel("SUPERCALIFRAGILISTIC", 50, 80, false)).toEqual({
      lines: ["SUPER…"],
      fontSize: 11,
    });
  });

  it("drops the label only when not even a few characters fit", () => {
    expect(treemapLabel("Communication Services", 30, 70, true)).toBeNull();
    expect(treemapLabel("Communication Services", 110, 12, false)).toBeNull();
  });
});
