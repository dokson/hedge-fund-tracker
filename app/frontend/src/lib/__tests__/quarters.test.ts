import { describe, it, expect } from "vitest";
import { isQuarter, assertQuarter, parseQuarters } from "../quarters";

describe("isQuarter", () => {
  it("accepts valid quarters", () => {
    expect(isQuarter("2025Q1")).toBe(true);
    expect(isQuarter("2026Q4")).toBe(true);
  });

  it("rejects invalid formats", () => {
    expect(isQuarter("2025")).toBe(false);
    expect(isQuarter("2025Q5")).toBe(false);
    expect(isQuarter("25Q1")).toBe(false);
    expect(isQuarter("Q1 2025")).toBe(false);
    expect(isQuarter("")).toBe(false);
  });
});

describe("assertQuarter", () => {
  it("returns valid quarter", () => {
    expect(assertQuarter("2025Q2")).toBe("2025Q2");
  });

  it("throws on invalid", () => {
    expect(() => assertQuarter("bogus")).toThrow(/Invalid quarter/);
  });
});

describe("parseQuarters", () => {
  it("filters invalid and sorts chronologically", () => {
    expect(parseQuarters(["2026Q1", "bogus", "2025Q4", "2025Q1"])).toEqual([
      "2025Q1",
      "2025Q4",
      "2026Q1",
    ]);
  });

  it("returns empty array for no valid entries", () => {
    expect(parseQuarters(["x", "y"])).toEqual([]);
  });
});
