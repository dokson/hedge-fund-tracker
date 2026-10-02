/**
 * Pins the non-quarterly de-duplication to the fixture shared with the Python
 * nq_position_key (tests/fixtures/nq_position_keys.json), so the web UI keeps
 * the same latest row per position as the backend.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { latestNQPerPosition, nqPositionKey } from "../data/nonQuarterly";
import type { NonQuarterlyFiling } from "../data/types";

const here = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(
  readFileSync(resolve(here, "../../../../../tests/fixtures/nq_position_keys.json"), "utf-8"),
) as {
  rows: Array<{ Fund: string; Ticker: string; CUSIP: string; Date: string; Filing_Date: string }>;
  keys: string[];
  surviving: number[];
};

const filings: NonQuarterlyFiling[] = fixture.rows.map((r) => ({
  fund: r.Fund,
  cusip: r.CUSIP,
  ticker: r.Ticker,
  company: "",
  shares: 0,
  value: "",
  avgPrice: "",
  date: r.Date,
  filingDate: r.Filing_Date,
}));

describe("non-quarterly position key parity with Python", () => {
  it("keys each row like nq_position_key", () => {
    expect(filings.map((f, i) => nqPositionKey(f, i))).toEqual(fixture.keys);
  });

  it("keeps the latest row per fund and position", () => {
    const kept = latestNQPerPosition(filings).map((f) => filings.indexOf(f));
    expect([...kept].sort((a, b) => a - b)).toEqual(fixture.surviving);
  });
});
