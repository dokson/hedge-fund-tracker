/**
 * Tests for the shared sector style registry. Used by the Sectors tab, the
 * stock-page sector pill, the Latest Filings sector chip, and the Fund Sector
 * Map — any drift in the lookup shows up as a colour swap across the app.
 */
import { describe, expect, it } from "vitest";

import { DEFAULT_SECTOR_STYLE, SECTOR_STYLE, getSectorStyle, sectorPillStyle } from "./sectorStyle";

describe("getSectorStyle", () => {
  it("returns the registered style for a known Yahoo sector", () => {
    expect(getSectorStyle("Technology")).toBe(SECTOR_STYLE.Technology);
    expect(getSectorStyle("Energy")).toBe(SECTOR_STYLE.Energy);
  });

  it("falls back to the default style for null / undefined / empty sector", () => {
    expect(getSectorStyle(null)).toBe(DEFAULT_SECTOR_STYLE);
    expect(getSectorStyle(undefined)).toBe(DEFAULT_SECTOR_STYLE);
    expect(getSectorStyle("")).toBe(DEFAULT_SECTOR_STYLE);
  });

  it("falls back to the default style for unknown sectors", () => {
    expect(getSectorStyle("Crypto Mining")).toBe(DEFAULT_SECTOR_STYLE);
  });

  it("keeps the neutral for unknown sectors only", () => {
    expect(DEFAULT_SECTOR_STYLE.token).toBe("muted-foreground");
    for (const style of Object.values(SECTOR_STYLE)) {
      expect(style.token).not.toBe("muted-foreground");
    }
  });

  it("every registered style exposes a token, its resolved colour and an icon", () => {
    for (const style of Object.values(SECTOR_STYLE)) {
      expect(style.token).toMatch(/^chart-[1-7]$/);
      expect(style.cssVar).toBe(`hsl(var(--${style.token}))`);
      expect(style.icon).toBeDefined();
    }
  });

  it("sectorPillStyle passes the hue inline, so nothing depends on the class scanner", () => {
    // The label reads on the neutral chip surface; the hue reaches the icon
    // alone through the custom property, so no 15% wash of the hue is emitted.
    expect(sectorPillStyle(SECTOR_STYLE.Technology!)).toEqual({
      "--sector-hue": "hsl(var(--chart-1))",
    });
  });
});
