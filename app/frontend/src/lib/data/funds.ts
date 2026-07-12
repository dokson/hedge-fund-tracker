/**
 * Hedge-fund loaders and hedge_funds/excluded CSV generation (Funds Config).
 */

import { cachedFetch, fetchCSV } from "./fetch";
import type { ExcludedHedgeFund, HedgeFund, RawHedgeFund } from "./types";

/** Converts a fund name to its filename form (spaces → underscores). */
export function fundNameToFileName(name: string): string {
  return name.replace(/ /g, "_");
}

/** Converts a filename form back to fund name (underscores → spaces). */
export function fileNameToFundName(name: string): string {
  return name.replace(/_/g, " ");
}

function rawToFund(r: RawHedgeFund): HedgeFund {
  return {
    cik: r.CIK,
    fund: r.Fund,
    manager: r.Manager,
    denomination: r.Denomination,
    ciks: r.CIKs,
    url: r.URL || "",
  };
}

const FUND_COLUMNS = [
  "CIK",
  "Fund",
  "Manager",
  "Denomination",
  "CIKs",
  "URL",
] as const satisfies readonly (keyof RawHedgeFund)[];

export async function getHedgeFunds(): Promise<HedgeFund[]> {
  return cachedFetch("hedge_funds", async () => {
    const raw = await fetchCSV<RawHedgeFund>("/database/hedge_funds.csv", FUND_COLUMNS);
    return raw.map(rawToFund);
  });
}

export async function getExcludedHedgeFunds(): Promise<ExcludedHedgeFund[]> {
  return cachedFetch("excluded_hedge_funds", async () => {
    const raw = await fetchCSV<RawHedgeFund>("/database/excluded_hedge_funds.csv", FUND_COLUMNS);
    return raw.map(rawToFund);
  });
}

const FUNDS_CSV_HEADER = '"CIK","Fund","Manager","Denomination","CIKs","URL"';

/** Quotes a CSV field, doubling embedded double quotes per RFC 4180. */
function csvQuote(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function fundsToCSV(funds: HedgeFund[]): string {
  const sorted = [...funds].sort((a, b) =>
    a.fund.localeCompare(b.fund, undefined, { sensitivity: "base" }),
  );
  return (
    FUNDS_CSV_HEADER +
    "\n" +
    sorted
      .map((f) => [f.cik, f.fund, f.manager, f.denomination, f.ciks, f.url].map(csvQuote).join(","))
      .join("\n") +
    "\n"
  );
}

/**
 * Generates a hedge_funds CSV string from an array of funds.
 */
export function generateHedgeFundsCSV(allFunds: HedgeFund[]): string {
  return fundsToCSV(allFunds);
}

/**
 * Generates an excluded_hedge_funds CSV string from an array of excluded funds.
 */
export function generateExcludedFundsCSV(allExcluded: ExcludedHedgeFund[]): string {
  return fundsToCSV(allExcluded);
}

/**
 * Generates updated hedge_funds CSV after adding a new fund.
 */
export function generateAddFundCSV(allFunds: HedgeFund[], newFund: HedgeFund): string {
  return fundsToCSV([...allFunds, newFund]);
}

/**
 * Generates updated CSVs after moving a fund from hedge_funds to excluded.
 */
export function generateDeleteFundCSVs(
  allFunds: HedgeFund[],
  excludedFunds: ExcludedHedgeFund[],
  fundToDelete: HedgeFund,
): { hedgeFundsCSV: string; excludedCSV: string } {
  const remaining = allFunds.filter((f) => f.cik !== fundToDelete.cik);
  const allExcluded = [...excludedFunds, fundToDelete];
  return {
    hedgeFundsCSV: fundsToCSV(remaining),
    excludedCSV: fundsToCSV(allExcluded),
  };
}

/**
 * Generates updated CSVs after restoring an excluded fund back to hedge_funds.
 */
export function generateRestoreFundCSVs(
  allFunds: HedgeFund[],
  excludedFunds: ExcludedHedgeFund[],
  fundToRestore: ExcludedHedgeFund,
): { hedgeFundsCSV: string; excludedCSV: string } {
  const updatedFunds = [...allFunds, fundToRestore];
  const remaining = excludedFunds.filter((f) => f.cik !== fundToRestore.cik);
  return {
    hedgeFundsCSV: fundsToCSV(updatedFunds),
    excludedCSV: fundsToCSV(remaining),
  };
}
