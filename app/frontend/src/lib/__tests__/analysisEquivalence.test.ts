/**
 * Equivalence guard: the TypeScript stock-level analysis must reproduce the
 * Python output bit-for-bit. Both sides assert against the same golden fixture
 * (tests/fixtures/analysis_golden.json), generated from the Python chain by
 * scripts/gen_analysis_golden.py. If either implementation drifts, this test
 * (or its Python twin) fails — so the two can't silently diverge.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { aggregateStockLevel, type FundTickerHolding } from "../dataService";

const here = dirname(fileURLToPath(import.meta.url));
const golden = JSON.parse(
  readFileSync(resolve(here, "../../../../../tests/fixtures/analysis_golden.json"), "utf-8"),
) as {
  input: Array<Record<string, number | string>>;
  expected: Record<string, Record<string, number | string>>;
};

function toHolding(row: Record<string, number | string>): FundTickerHolding {
  return {
    fund: String(row.Fund),
    ticker: String(row.Ticker),
    company: String(row.Company),
    shares: Number(row.Shares),
    deltaShares: Number(row.Delta_Shares),
    value: Number(row.Value),
    deltaValue: Number(row.Delta_Value),
    portfolioPct: Number(row.Portfolio_Pct),
    portfolioPctRank: Number(row.Portfolio_Pct_Rank),
    fundConcentrationRatio: Number(row.Fund_Concentration_Ratio),
    sharesDeltaPct: Number(row.Shares_Delta_Pct),
    delta: "",
    isBuyer: false,
    isSeller: false,
    isHolder: false,
    isNew: false,
    isClosed: false,
    isHighConviction: false,
  };
}

const round4 = (n: number) => Math.round(n * 10000) / 10000;

describe("aggregateStockLevel matches the Python golden fixture", () => {
  const result = aggregateStockLevel(golden.input.map(toHolding));
  const byTicker = new Map(result.map((s) => [s.ticker, s as unknown as Record<string, number>]));

  it("produces exactly the expected tickers", () => {
    expect([...byTicker.keys()].sort()).toEqual(Object.keys(golden.expected).sort());
  });

  for (const [ticker, expected] of Object.entries(golden.expected)) {
    describe(ticker, () => {
      for (const [field, rawExpected] of Object.entries(expected)) {
        it(field, () => {
          const actual = byTicker.get(ticker)![field];
          if (rawExpected === "Infinity") {
            expect(actual).toBe(Infinity);
          } else {
            expect(round4(actual)).toBe(rawExpected);
          }
        });
      }
    });
  }
});
