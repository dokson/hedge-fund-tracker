/**
 * Quarter discovery and per-fund 13F holdings loaders (mirrors the Python
 * app/database/quarters.py responsibilities on the client side).
 */

import { BASE_PATH, IS_GH_PAGES_MODE } from "../config";
import { parseQuarters, type Quarter } from "../quarters";
import { cachedFetch, fetchCSV } from "./fetch";
import { formatPct, formatValueShort, parseValueString } from "./format";
import { fundNameToFileName } from "./funds";
import type { QuarterlyHolding, RawQuarterlyHolding } from "./types";

/**
 * Fetches the list of available quarter folders, sorted chronologically.
 * Derives from /api/database/quarters locally or metadata.json in GH Pages mode.
 */
export async function getAvailableQuarters(): Promise<readonly Quarter[]> {
  if (IS_GH_PAGES_MODE) {
    const response = await fetch(`${BASE_PATH}/database/metadata.json`);
    if (!response.ok) throw new Error("Failed to load metadata.json");
    const metadata: { quarters?: string[] } = await response.json();
    return parseQuarters(metadata.quarters ?? []);
  }
  const response = await fetch(`${window.location.origin}/api/database/quarters`);
  if (!response.ok) throw new Error("Failed to list quarters");
  const raw: string[] = await response.json();
  return parseQuarters(raw);
}

/**
 * Returns the most recent quarter as resolved by the backend, or null if none exist.
 * Backend is the single source of truth; frontend does not sort the quarter list itself.
 * Caching is intentionally delegated to react-query at the call site.
 */
export async function getLatestQuarter(): Promise<Quarter | null> {
  if (IS_GH_PAGES_MODE) {
    const quarters = await getAvailableQuarters();
    return quarters.at(-1) ?? null;
  }
  const response = await fetch(`${window.location.origin}/api/database/quarters/latest`);
  if (!response.ok) throw new Error("Failed to fetch latest quarter");
  const data: { quarter: string | null } = await response.json();
  if (!data.quarter) return null;
  return parseQuarters([data.quarter])[0] ?? null;
}

/** Returns only the quarters where a specific fund has data (sorted chronologically). */
export async function getFundAvailableQuarters(fundName: string): Promise<Quarter[]> {
  return cachedFetch(`fund_quarters_${fundName}`, async () => {
    const fileName = fundNameToFileName(fundName);
    const quarters = await getAvailableQuarters();
    const results = await Promise.all(
      quarters.map(async (q) => {
        try {
          const fundList = await getQuarterFundList(q);
          return fundList.includes(fileName) ? q : null;
        } catch {
          return null;
        }
      }),
    );
    return results.filter((q): q is Quarter => q !== null);
  });
}

export async function getQuarterFundList(quarter: string): Promise<string[]> {
  return cachedFetch(`quarter_funds_${quarter}`, async () => {
    if (IS_GH_PAGES_MODE) {
      // In GH Pages mode, read from bundled manifest.json
      const response = await fetch(`${BASE_PATH}/database/${quarter}/manifest.json`);
      if (!response.ok) throw new Error(`No data available for ${quarter}`);
      const manifest: unknown = await response.json();
      if (!Array.isArray(manifest) || !manifest.every((f) => typeof f === "string")) {
        throw new Error(`Malformed manifest.json for ${quarter}`);
      }
      return manifest;
    }
    const response = await fetch(`${window.location.origin}/api/database/quarters/${quarter}`);
    if (!response.ok) throw new Error(`Failed to list funds for ${quarter}`);
    const files: string[] = await response.json();
    return files;
  });
}

export async function getFundQuarterlyHoldings(
  quarter: string,
  fundName: string,
): Promise<QuarterlyHolding[]> {
  const key = `holdings_${quarter}_${fundName}`;
  return cachedFetch(key, async () => {
    const raw = await fetchCSV<RawQuarterlyHolding>(
      `/database/${quarter}/${encodeURIComponent(fundNameToFileName(fundName))}.csv`,
      [
        "CUSIP",
        "Ticker",
        "Company",
        "Shares",
        "Delta_Shares",
        "Value",
        "Delta_Value",
        "Delta",
        "Portfolio%",
      ] satisfies readonly (keyof RawQuarterlyHolding)[],
    );
    return raw.map((r) => ({
      cusip: r.CUSIP,
      ticker: r.Ticker,
      company: r.Company,
      shares: parseInt(r.Shares, 10) || 0,
      deltaShares: r.Delta_Shares === "" ? 0 : parseInt(r.Delta_Shares, 10) || 0,
      value: r.Value,
      deltaValue: r.Delta_Value,
      delta: r.Delta,
      portfolioPct: parseFloat(r["Portfolio%"]) || 0,
    }));
  });
}

/**
 * Aggregates per-CUSIP holdings into one row per ticker.
 *
 * A fund can report the same ticker under several CUSIPs (e.g. common stock
 * plus a 13F-reportable convertible note, or multiple share classes). The
 * per-ticker views — stock page, multi-fund consensus, and the CLI fund
 * analysis — all collapse these into a single line; this helper gives the
 * fund-portfolio view the same behaviour. Shares, deltas, values and portfolio
 * percentages are summed, and the Δ label is recomputed from the aggregated
 * shares. Tickers backed by a single CUSIP are returned unchanged so their
 * original formatting is preserved exactly. The synthetic "Total" row is
 * dropped.
 */
export function aggregateHoldingsByTicker(holdings: QuarterlyHolding[]): QuarterlyHolding[] {
  const groups = new Map<
    string,
    { base: QuarterlyHolding; value: number; deltaValue: number; count: number }
  >();

  for (const h of holdings) {
    if (h.cusip === "Total") continue;
    const value = parseValueString(h.value);
    const deltaValue = parseValueString(h.deltaValue);
    const existing = groups.get(h.ticker);
    if (existing) {
      existing.base.shares += h.shares;
      existing.base.deltaShares += h.deltaShares;
      existing.base.portfolioPct += h.portfolioPct;
      existing.value += value;
      existing.deltaValue += deltaValue;
      existing.count += 1;
    } else {
      groups.set(h.ticker, { base: { ...h }, value, deltaValue, count: 1 });
    }
  }

  return [...groups.values()].map(({ base, value, deltaValue, count }) => {
    if (count === 1) return base;
    const prevShares = base.shares - base.deltaShares;
    let delta: string;
    if (base.shares === 0) delta = "CLOSE";
    else if (base.deltaShares === 0) delta = "NO CHANGE";
    else if (base.shares === base.deltaShares) delta = "NEW";
    else delta = formatPct(prevShares > 0 ? (base.deltaShares / prevShares) * 100 : 0, true);
    return {
      ...base,
      value: formatValueShort(value),
      deltaValue: formatValueShort(deltaValue),
      delta,
    };
  });
}
