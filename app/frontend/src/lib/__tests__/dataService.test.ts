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
  it.each([
    ["", 0],
    ["N/A", 0],
    ["1234", 1234],
    ["$500", 500],
    ["1,234,567", 1234567],
    ["1.5B", 1_500_000_000],
    ["2.5M", 2_500_000],
    ["500K", 500_000],
    ["-1.2M", -1_200_000],
    ["$3.75M", 3_750_000],
  ])("parses %j as %d", (input, expected) => {
    expect(parseValueString(input)).toBe(expected);
  });
});

describe("formatValue", () => {
  it.each([
    [0, "$0"],
    [500, "$500"],
    [5000, "$5K"],
    [2_500_000, "$2.50M"],
    [1_500_000_000, "$1.50B"],
    [2_000_000_000_000, "$2.00T"],
    [-1_500_000, "$-1.50M"],
  ])("formats %d as %s", (input, expected) => {
    expect(formatValue(input)).toBe(expected);
  });
});

describe("formatPct", () => {
  it.each([Infinity, -Infinity, NaN])("returns NEW for %d", (input) => {
    expect(formatPct(input)).toBe("NEW");
  });

  it.each([
    [12.5, undefined, "12.5%"],
    [-8.3, undefined, "-8.3%"],
    [12.5, true, "+12.5%"],
    [-8.3, true, "-8.3%"],
    [12.5, false, "12.5%"],
  ])("formats %d (showSign=%s) as %s", (input, showSign, expected) => {
    expect(formatPct(input, showSign)).toBe(expected);
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
});
