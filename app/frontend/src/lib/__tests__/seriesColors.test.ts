import { describe, expect, it } from "vitest";

import { SERIES_COLORS, seriesColor } from "../seriesColors";

describe("series colours", () => {
  it("gives the smart score its own yellow, never a hue another series uses", () => {
    expect(seriesColor("smart_score")).toBe("hsl(var(--chart-8))");
    const others = Object.entries(SERIES_COLORS)
      .filter(([id]) => id !== "smart_score")
      .map(([, colour]) => colour);
    expect(others).not.toContain(seriesColor("smart_score"));
  });
});
