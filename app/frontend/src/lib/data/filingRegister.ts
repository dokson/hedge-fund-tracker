/**
 * The filing register (database/filing_anomalies.csv) read on top of the saved
 * quarter CSVs. The register is the single source of the restated figures: this
 * module only copies them, mirroring app/database/filing_anomalies.py
 * (apply_restatements), pinned by tests/fixtures/restatement_cases.json.
 */

import { cachedFetch, fetchCSV, HttpError } from "./fetch";
import { parseValueString } from "./format";
import type { QuarterlyHolding } from "./types";

export interface RegisterRow {
  Quarter: string;
  Fund: string;
  Filed_CUSIP: string;
  Status: string;
  Kind: string;
  Shares: string;
  Value: string;
  Delta_Shares: string;
  Delta_Value: string;
  Delta: string;
}

const REGISTER_COLUMNS = [
  "Quarter",
  "Fund",
  "Filed_CUSIP",
  "Status",
  "Kind",
  "Shares",
  "Value",
  "Delta_Shares",
  "Delta_Value",
  "Delta",
] as const satisfies readonly (keyof RegisterRow)[];

const APPLIED = new Set(["auto-corrected", "corrected", "carried"]);
const RESTATED_KINDS = new Set(["value", "shares", "carried"]);

/** The register; a database without one restates nothing. */
export async function getFilingRegister(): Promise<RegisterRow[]> {
  return cachedFetch("filing_register", async () => {
    try {
      return await fetchCSV<RegisterRow>("/database/filing_anomalies.csv", REGISTER_COLUMNS);
    } catch (err) {
      if (err instanceof HttpError && err.status === 404) return [];
      throw err;
    }
  });
}

/**
 * One filing's holdings with the register's restated figures, its Portfolio%
 * re-weighted when anything changed. The input is never mutated.
 */
export function applyRestatements(
  holdings: readonly QuarterlyHolding[],
  register: readonly RegisterRow[],
  quarter: string,
  fund: string,
): QuarterlyHolding[] {
  const fixes = new Map(
    register
      .filter(
        (r) =>
          r.Quarter === quarter &&
          r.Fund === fund &&
          APPLIED.has(r.Status) &&
          RESTATED_KINDS.has(r.Kind),
      )
      .map((r) => [r.Filed_CUSIP, r] as const),
  );
  if (fixes.size === 0 || !holdings.some((h) => fixes.has(h.cusip))) return [...holdings];

  const restated = holdings.map((h) => {
    const fix = fixes.get(h.cusip);
    if (!fix) return { ...h };
    return {
      ...h,
      shares: Number(fix.Shares),
      deltaShares: Number(fix.Delta_Shares),
      value: fix.Value,
      deltaValue: fix.Delta_Value,
      delta: fix.Delta,
    };
  });
  const positions = restated.filter((h) => h.cusip !== "Total");
  const total = positions.reduce((sum, h) => sum + parseValueString(h.value), 0);
  if (total <= 0) return restated;
  return restated.map((h) =>
    h.cusip === "Total" ? h : { ...h, portfolioPct: (parseValueString(h.value) / total) * 100 },
  );
}
