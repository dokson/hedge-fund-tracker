/**
 * Stock universe loaders: stocks.csv plus the sector hierarchy that derives
 * each stock's Sector from its Industry at read time.
 */

import { cachedFetch, fetchCSV } from "./fetch";
import type { RawSectorHierarchy, RawStock, SectorHierarchyEntry, Stock } from "./types";

export async function getStocks(): Promise<Stock[]> {
  return cachedFetch("stocks", async () => {
    const [raw, hierarchy] = await Promise.all([
      fetchCSV<RawStock>("/database/stocks.csv", [
        "CUSIP",
        "Ticker",
        "Company",
      ] satisfies readonly (keyof RawStock)[]),
      getSectorHierarchy(),
    ]);
    // Derive the Sector from the Industry via sector_hierarchy.csv —
    // stocks.csv intentionally stores only the Industry to avoid duplication.
    const industryToSector = new Map(hierarchy.map((h) => [h.industry, h.sector]));
    return raw.map((r) => ({
      cusip: r.CUSIP,
      ticker: r.Ticker,
      company: r.Company,
      industry: r.Industry || undefined,
      sector: r.Industry ? industryToSector.get(r.Industry) : undefined,
    }));
  });
}

export async function getSectorHierarchy(): Promise<SectorHierarchyEntry[]> {
  return cachedFetch("sector_hierarchy", async () => {
    const raw = await fetchCSV<RawSectorHierarchy>("/database/sector_hierarchy.csv", [
      "Sector",
      "Industry",
      "Count",
    ] satisfies readonly (keyof RawSectorHierarchy)[]);
    return raw.map((r) => ({
      sector: r.Sector,
      industry: r.Industry,
      count: parseInt(r.Count, 10) || 0,
    }));
  });
}
