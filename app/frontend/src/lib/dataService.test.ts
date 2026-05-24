/**
 * Tests for the stocks/sector-hierarchy JOIN inside getStocks().
 *
 * stocks.csv intentionally stores only the Industry — the Sector is derived
 * at read time by joining with sector_hierarchy.csv. These tests ensure that
 * derivation happens correctly and degrades gracefully when the hierarchy is
 * missing an Industry entry.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";

import { clearCache, getStocks } from "./dataService";

interface MockResponse {
  ok: boolean;
  text: () => Promise<string>;
}

function csvResponse(body: string): MockResponse {
  return { ok: true, text: async () => body };
}

const STOCKS_CSV = `"CUSIP","Ticker","Company","Industry"
"037833100","AAPL","Apple Inc","Consumer Electronics"
"594918104","MSFT","Microsoft Corp","Software - Infrastructure"
"99999999X","WEIRD","Unknown Industry Co","NotInHierarchy"
"00000000A","BLANK","No Industry Co",""
`;

const HIERARCHY_CSV = `"Sector","Industry"
"Technology","Consumer Electronics"
"Technology","Software - Infrastructure"
`;

describe("getStocks", () => {
  beforeEach(() => {
    clearCache();
    vi.restoreAllMocks();
  });

  it("derives the Sector from the Industry via sector_hierarchy.csv", async () => {
    vi.spyOn(global, "fetch").mockImplementation((async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : (input as URL).toString();
      if (url.includes("stocks.csv")) return csvResponse(STOCKS_CSV) as Response;
      if (url.includes("sector_hierarchy.csv")) return csvResponse(HIERARCHY_CSV) as Response;
      throw new Error(`Unexpected fetch: ${url}`);
    }) as unknown as typeof fetch);

    const stocks = await getStocks();
    const aapl = stocks.find((s) => s.ticker === "AAPL");
    const msft = stocks.find((s) => s.ticker === "MSFT");

    expect(aapl?.industry).toBe("Consumer Electronics");
    expect(aapl?.sector).toBe("Technology");
    expect(msft?.sector).toBe("Technology");
  });

  it("leaves sector undefined when the Industry is not in the hierarchy", async () => {
    vi.spyOn(global, "fetch").mockImplementation((async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : (input as URL).toString();
      if (url.includes("stocks.csv")) return csvResponse(STOCKS_CSV) as Response;
      if (url.includes("sector_hierarchy.csv")) return csvResponse(HIERARCHY_CSV) as Response;
      throw new Error(`Unexpected fetch: ${url}`);
    }) as unknown as typeof fetch);

    const stocks = await getStocks();
    const weird = stocks.find((s) => s.ticker === "WEIRD");

    expect(weird?.industry).toBe("NotInHierarchy");
    expect(weird?.sector).toBeUndefined();
  });

  it("leaves both industry and sector undefined when stocks.csv has empty Industry", async () => {
    vi.spyOn(global, "fetch").mockImplementation((async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : (input as URL).toString();
      if (url.includes("stocks.csv")) return csvResponse(STOCKS_CSV) as Response;
      if (url.includes("sector_hierarchy.csv")) return csvResponse(HIERARCHY_CSV) as Response;
      throw new Error(`Unexpected fetch: ${url}`);
    }) as unknown as typeof fetch);

    const stocks = await getStocks();
    const blank = stocks.find((s) => s.ticker === "BLANK");

    expect(blank?.industry).toBeUndefined();
    expect(blank?.sector).toBeUndefined();
  });
});
