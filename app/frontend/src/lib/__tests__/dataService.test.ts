import { describe, it, expect } from "vitest";
import { parseValueString, formatValue, formatPct } from "../dataService";

describe("parseValueString", () => {
  it("should return 0 for empty string", () => {
    expect(parseValueString("")).toBe(0);
  });

  it("should return 0 for N/A", () => {
    expect(parseValueString("N/A")).toBe(0);
  });

  it("should parse plain number", () => {
    expect(parseValueString("1234")).toBe(1234);
  });

  it("should parse number with dollar sign", () => {
    expect(parseValueString("$500")).toBe(500);
  });

  it("should parse number with commas", () => {
    expect(parseValueString("1,234,567")).toBe(1234567);
  });

  it("should parse number with B suffix", () => {
    expect(parseValueString("1.5B")).toBe(1_500_000_000);
  });

  it("should parse number with M suffix", () => {
    expect(parseValueString("2.5M")).toBe(2_500_000);
  });

  it("should parse number with K suffix", () => {
    expect(parseValueString("500K")).toBe(500_000);
  });

  it("should parse negative number with M suffix", () => {
    expect(parseValueString("-1.2M")).toBe(-1_200_000);
  });

  it("should parse dollar amount with M suffix", () => {
    expect(parseValueString("$3.75M")).toBe(3_750_000);
  });
});

describe("formatValue", () => {
  it("should format zero", () => {
    expect(formatValue(0)).toBe("$0");
  });

  it("should format small number", () => {
    expect(formatValue(500)).toBe("$500");
  });

  it("should format thousands", () => {
    expect(formatValue(5000)).toBe("$5K");
  });

  it("should format millions", () => {
    expect(formatValue(2_500_000)).toBe("$2.50M");
  });

  it("should format billions", () => {
    expect(formatValue(1_500_000_000)).toBe("$1.50B");
  });

  it("should format trillions", () => {
    expect(formatValue(2_000_000_000_000)).toBe("$2.00T");
  });

  it("should format negative values", () => {
    expect(formatValue(-1_500_000)).toBe("$-1.50M");
  });
});

describe("formatPct", () => {
  it("should return NEW for Infinity", () => {
    expect(formatPct(Infinity)).toBe("NEW");
  });

  it("should return NEW for -Infinity", () => {
    expect(formatPct(-Infinity)).toBe("NEW");
  });

  it("should return NEW for NaN", () => {
    expect(formatPct(NaN)).toBe("NEW");
  });

  it("should format positive percentage", () => {
    expect(formatPct(12.5)).toBe("12.5%");
  });

  it("should format negative percentage", () => {
    expect(formatPct(-8.3)).toBe("-8.3%");
  });

  it("should add sign when showSign is true and value is positive", () => {
    expect(formatPct(12.5, true)).toBe("+12.5%");
  });

  it("should not add sign for negative values even with showSign", () => {
    expect(formatPct(-8.3, true)).toBe("-8.3%");
  });

  it("should not add sign when showSign is false", () => {
    expect(formatPct(12.5, false)).toBe("12.5%");
  });
});
