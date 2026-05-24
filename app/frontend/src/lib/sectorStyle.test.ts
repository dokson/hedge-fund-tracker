/**
 * Tests for the shared sector style registry. Used by the Sectors tab, the
 * stock-page sector pill, the Latest Filings sector chip, and the Fund Sector
 * Map — any drift in the lookup shows up as a colour swap across the app.
 */
import { describe, expect, it } from "vitest";

import { DEFAULT_SECTOR_STYLE, SECTOR_STYLE, getSectorStyle } from "./sectorStyle";

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

  it("every registered style exposes the four token classes used by chips", () => {
    for (const style of Object.values(SECTOR_STYLE)) {
      expect(style.color).toMatch(/^text-/);
      expect(style.bg).toMatch(/^bg-/);
      expect(style.border).toMatch(/^border-/);
      expect(style.dot).toMatch(/^bg-/);
      expect(style.icon).toBeDefined();
    }
  });
});
