import { describe, it, expect } from "vitest";
import {
  parseValueString,
  formatValue,
  formatPct,
  aggregateHoldingsByTicker,
  generateAddFundCSV,
  generateRestoreFundCSVs,
  type HedgeFund,
  type ExcludedHedgeFund,
  type QuarterlyHolding,
} from "../dataService";

const mkFund = (cik: string, fund: string): HedgeFund => ({
  cik,
  fund,
  manager: "M",
  denomination: "D",
  ciks: "",
  url: "",
});

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

describe("aggregateHoldingsByTicker", () => {
  const mkHolding = (over: Partial<QuarterlyHolding>): QuarterlyHolding => ({
    cusip: "X",
    ticker: "X",
    company: "X",
    shares: 0,
    deltaShares: 0,
    value: "0",
    deltaValue: "0",
    delta: "NO CHANGE",
    portfolioPct: 0,
    ...over,
  });

  it("merges multiple CUSIPs of the same ticker into a single row", () => {
    // Real case: Cyrus holds EchoStar (SATS) under both a common-stock CUSIP
    // and a debt CUSIP. The fund view must show one consolidated SATS line.
    const result = aggregateHoldingsByTicker([
      mkHolding({
        cusip: "278768106",
        ticker: "SATS",
        company: "Echostar Corp",
        shares: 576571,
        deltaShares: 0,
        value: "67.5M",
        deltaValue: "0",
        delta: "NO CHANGE",
        portfolioPct: 34.4,
      }),
      mkHolding({
        cusip: "278768AB2",
        ticker: "SATS",
        company: "Echostar Corp",
        shares: 12932027,
        deltaShares: -11600000,
        value: "46.19M",
        deltaValue: "-41.44M",
        delta: "-47.3%",
        portfolioPct: 23.5,
      }),
    ]);

    expect(result).toHaveLength(1);
    const sats = result[0];
    expect(sats.ticker).toBe("SATS");
    expect(sats.shares).toBe(13508598);
    expect(sats.deltaShares).toBe(-11600000);
    expect(sats.value).toBe("113.69M");
    expect(sats.deltaValue).toBe("-41.44M");
    expect(sats.portfolioPct).toBeCloseTo(57.9);
    expect(sats.delta).toBe("-46.2%");
  });

  it("returns single-CUSIP holdings unchanged", () => {
    const gtx = mkHolding({
      cusip: "366505105",
      ticker: "GTX",
      company: "Garrett Motion Inc",
      shares: 2159866,
      deltaShares: -4692131,
      value: "39.24M",
      deltaValue: "-85.26M",
      delta: "-68.5%",
      portfolioPct: 20,
    });
    expect(aggregateHoldingsByTicker([gtx])).toEqual([gtx]);
  });

  it("drops the synthetic Total row", () => {
    expect(aggregateHoldingsByTicker([mkHolding({ cusip: "Total", ticker: "" })])).toHaveLength(0);
  });
});

describe("hedge_funds CSV alphabetical ordering", () => {
  const existing: HedgeFund[] = [
    mkFund("001", "Charlie"),
    mkFund("002", "apple"),
    mkFund("003", "delta"),
  ];

  it("generateAddFundCSV inserts the new fund at correct alphabetical position (case-insensitive)", () => {
    const csv = generateAddFundCSV(existing, mkFund("099", "Bravo"));
    const fundColumn = csv
      .trim()
      .split("\n")
      .slice(1)
      .map((line) => line.split(",")[1].replace(/"/g, ""));
    expect(fundColumn).toEqual(["apple", "Bravo", "Charlie", "delta"]);
  });

  it("generateRestoreFundCSVs places the restored fund alphabetically in hedge_funds.csv", () => {
    const excluded: ExcludedHedgeFund[] = [mkFund("099", "Bravo"), mkFund("100", "Other")];
    const { hedgeFundsCSV, excludedCSV } = generateRestoreFundCSVs(existing, excluded, excluded[0]);
    const hedgeFunds = hedgeFundsCSV
      .trim()
      .split("\n")
      .slice(1)
      .map((l) => l.split(",")[1].replace(/"/g, ""));
    expect(hedgeFunds).toEqual(["apple", "Bravo", "Charlie", "delta"]);
    const remainingExcluded = excludedCSV
      .trim()
      .split("\n")
      .slice(1)
      .map((l) => l.split(",")[1].replace(/"/g, ""));
    expect(remainingExcluded).toEqual(["Other"]);
  });
});

describe("hedge_funds CSV quote escaping (RFC 4180)", () => {
  it("escapes embedded double quotes so the CSV round-trips", () => {
    const fund: HedgeFund = {
      cik: "001",
      fund: 'John "JJ" Capital',
      manager: 'A "B" C',
      denomination: "Plain",
      ciks: "",
      url: "",
    };
    const csv = generateAddFundCSV([], fund);
    const dataLine = csv.trim().split("\n")[1];
    // Embedded quotes are doubled per RFC 4180.
    expect(dataLine).toContain('"John ""JJ"" Capital"');
    expect(dataLine).toContain('"A ""B"" C"');
  });

  it("does not alter fields without quotes", () => {
    const csv = generateAddFundCSV([], mkFund("001", "Acme"));
    expect(csv.trim().split("\n")[1]).toBe('"001","Acme","M","D","",""');
  });
});
