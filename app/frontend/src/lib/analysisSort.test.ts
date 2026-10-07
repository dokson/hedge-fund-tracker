import { describe, expect, it } from "vitest";

import { sortAnalysisRows } from "./analysisSort";
import type { StockQuarterAnalysis } from "./data/types";

function row(overrides: Partial<StockQuarterAnalysis>): StockQuarterAnalysis {
  return {
    ticker: "AAA",
    company: "A Corp",
    totalValue: 0,
    totalDeltaValue: 0,
    maxPortfolioPct: 0,
    avgPortfolioPct: 0,
    buyerCount: 0,
    sellerCount: 0,
    holderCount: 0,
    newHolderCount: 0,
    closeCount: 0,
    highConvictionCount: 0,
    netBuyers: 0,
    buyerSellerRatio: 0,
    ownershipDeltaAvg: 0,
    fundConcentrationAvg: 0,
    delta: 0,
    ...overrides,
  };
}

const tickers = (rows: StockQuarterAnalysis[]) => rows.map((r) => r.ticker);

describe("sortAnalysisRows", () => {
  it("orders by the numeric field in either direction, without touching the input", () => {
    const input = [
      row({ ticker: "B", holderCount: 5 }),
      row({ ticker: "A", holderCount: 9 }),
      row({ ticker: "C", holderCount: 1 }),
    ];
    expect(tickers(sortAnalysisRows(input, "holderCount", "desc"))).toEqual(["A", "B", "C"]);
    expect(tickers(sortAnalysisRows(input, "holderCount", "asc"))).toEqual(["C", "B", "A"]);
    expect(tickers(input)).toEqual(["B", "A", "C"]);
  });

  it("puts an infinite delta (an all-new stock) first descending and last ascending", () => {
    const input = [
      row({ ticker: "A", delta: 12 }),
      row({ ticker: "N", delta: Infinity }),
      row({ ticker: "B", delta: 40 }),
    ];
    expect(tickers(sortAnalysisRows(input, "delta", "desc"))).toEqual(["N", "B", "A"]);
    expect(tickers(sortAnalysisRows(input, "delta", "asc"))).toEqual(["A", "B", "N"]);
  });

  it("breaks a tie on the shown Smart Score by the unrounded composite, descending", () => {
    const perfect = row({
      ticker: "P",
      smartScore: 10,
      scoreBreadth: 100,
      scoreMomentum: 100,
      scoreConviction: 100,
    });
    const almost = row({
      ticker: "Q",
      smartScore: 10,
      scoreBreadth: 99.6,
      scoreMomentum: 99.6,
      scoreConviction: 100,
    });
    expect(tickers(sortAnalysisRows([almost, perfect], "smartScore", "desc"))).toEqual(["P", "Q"]);
  });

  it("reverses the whole Smart Score order, tie-break included, ascending", () => {
    const perfect = row({
      ticker: "P",
      smartScore: 10,
      scoreBreadth: 100,
      scoreMomentum: 100,
      scoreConviction: 100,
    });
    const almost = row({
      ticker: "Q",
      smartScore: 10,
      scoreBreadth: 99.6,
      scoreMomentum: 99.6,
      scoreConviction: 100,
    });
    const low = row({
      ticker: "L",
      smartScore: 4,
      scoreBreadth: 30,
      scoreMomentum: 30,
      scoreConviction: 30,
    });
    expect(tickers(sortAnalysisRows([perfect, low, almost], "smartScore", "asc"))).toEqual([
      "L",
      "Q",
      "P",
    ]);
  });
});
