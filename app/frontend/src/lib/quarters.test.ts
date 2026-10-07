import { describe, expect, it } from "vitest";

import { filingFreshness, latestUsableQuarter, quartersBehind } from "./quarters";

describe("quartersBehind", () => {
  it("is 0 for a fund on the board's quarter, and for one already past it", () => {
    expect(quartersBehind("2026Q2", "2026Q2")).toBe(0);
    expect(quartersBehind("2026Q3", "2026Q2")).toBe(0);
  });

  it("counts whole quarters, across a year boundary too", () => {
    expect(quartersBehind("2026Q1", "2026Q2")).toBe(1);
    expect(quartersBehind("2025Q4", "2026Q1")).toBe(1);
    expect(quartersBehind("2025Q3", "2026Q2")).toBe(3);
  });

  it("is null when either quarter is unknown", () => {
    expect(quartersBehind(null, "2026Q2")).toBeNull();
    expect(quartersBehind("2026Q2", null)).toBeNull();
  });
});

describe("filingFreshness", () => {
  it("is current for a fund on the board's quarter or past it", () => {
    expect(filingFreshness("2026Q2", "2026Q2")).toBe("current");
    expect(filingFreshness("2026Q3", "2026Q2")).toBe("current");
  });

  it("is late up to two quarters behind", () => {
    expect(filingFreshness("2026Q1", "2026Q2")).toBe("late");
    expect(filingFreshness("2025Q4", "2026Q2")).toBe("late");
  });

  it("is stale beyond two quarters behind", () => {
    expect(filingFreshness("2025Q3", "2026Q2")).toBe("stale");
    expect(filingFreshness("2024Q1", "2026Q2")).toBe("stale");
  });

  it("is null when either quarter is unknown", () => {
    expect(filingFreshness(null, "2026Q2")).toBeNull();
    expect(filingFreshness("2026Q2", null)).toBeNull();
  });
});

describe("latestUsableQuarter", () => {
  it("skips a newest quarter with under half the filings of the last usable one", () => {
    expect(latestUsableQuarter({ "2026Q2": 140, "2026Q3": 1 })).toBe("2026Q2");
  });

  it("accepts exactly half", () => {
    expect(latestUsableQuarter({ "2026Q2": 140, "2026Q3": 70 })).toBe("2026Q3");
  });

  it("does not take an incomplete quarter as the baseline for the next one", () => {
    expect(latestUsableQuarter({ "2026Q1": 10, "2026Q2": 2, "2026Q3": 1 })).toBe("2026Q1");
  });

  it("orders by quarter, not by key insertion", () => {
    expect(latestUsableQuarter({ "2026Q3": 1, "2026Q2": 140 })).toBe("2026Q2");
  });

  it("is null without quarters", () => {
    expect(latestUsableQuarter({})).toBeNull();
  });
});
