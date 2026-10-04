/**
 * Equivalence guard: the TypeScript loader reads the filing register exactly as
 * the Python one (app/database/filing_anomalies.py::apply_restatements). Both
 * assert against tests/fixtures/restatement_cases.json.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { applyRestatements, type RegisterRow } from "../data/filingRegister";
import { parseValueString } from "../data/format";
import type { QuarterlyHolding } from "../data/types";

const here = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(
  readFileSync(resolve(here, "../../../../../tests/fixtures/restatement_cases.json"), "utf-8"),
) as {
  quarter: string;
  fund: string;
  register: RegisterRow[];
  holdings: Array<Record<string, string>>;
  expected: Array<{
    cusip: string;
    shares: number;
    deltaShares: number;
    value: number;
    deltaValue: number;
    delta: string;
    portfolioPct: number;
  }>;
};

function toHolding(row: Record<string, string>): QuarterlyHolding {
  return {
    cusip: row.CUSIP ?? "",
    ticker: "",
    company: "",
    shares: Number(row.Shares),
    deltaShares: Number(row.Delta_Shares),
    value: row.Value ?? "",
    deltaValue: row.Delta_Value ?? "",
    delta: row.Delta ?? "",
    portfolioPct: parseFloat(row["Portfolio%"] ?? "") || 0,
  };
}

describe("applyRestatements", () => {
  const out = applyRestatements(
    fixture.holdings.map(toHolding),
    fixture.register,
    fixture.quarter,
    fixture.fund,
  );

  it.each(fixture.expected)("matches the shared case for $cusip", (expected) => {
    const got = out.find((h) => h.cusip === expected.cusip);
    expect(got).toBeDefined();
    if (!got) return;
    expect(got.shares).toBe(expected.shares);
    expect(got.deltaShares).toBe(expected.deltaShares);
    expect(parseValueString(got.value)).toBeCloseTo(expected.value, 0);
    expect(parseValueString(got.deltaValue)).toBeCloseTo(expected.deltaValue, 0);
    expect(got.delta).toBe(expected.delta);
    expect(got.portfolioPct).toBeCloseTo(expected.portfolioPct, 1);
  });

  it("leaves a filing with nothing to restate untouched", () => {
    const holdings = fixture.holdings.map(toHolding);
    expect(applyRestatements(holdings, fixture.register, "2024Q4", fixture.fund)).toEqual(holdings);
  });

  it("skips the Total line when re-weighting", () => {
    const total: QuarterlyHolding = { ...toHolding(fixture.holdings[0] ?? {}), cusip: "Total" };
    const result = applyRestatements(
      [...fixture.holdings.map(toHolding), total],
      fixture.register,
      fixture.quarter,
      fixture.fund,
    );
    expect(result.find((h) => h.cusip === "FXI")?.portfolioPct).toBeCloseTo(36.8, 1);
  });
});
