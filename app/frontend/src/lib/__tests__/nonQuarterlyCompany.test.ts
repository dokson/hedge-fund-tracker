/**
 * non_quarterly.csv stores the company name exactly as filed, so the display
 * name is resolved from stocks.csv (the canonical, normalized CUSIP → Company
 * map) with the as-filed name as fallback.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearCache } from "../data/fetch";
import { getNonQuarterlyFilings } from "../data/nonQuarterly";

const NQ_CSV = `"Fund","CUSIP","Ticker","Company","Shares","Value","Avg_Price","Date","Filing_Date"
"Spruce House","36262G101","GXO","Gxo Logistics, Inc.","6003988","293.84M","48.94","2026-07-14","2026-07-21"
"Helikon","999999999","ZZZ","Untracked Holdings, Inc. Common Stock","100","1.00M","10.00","2026-07-10","2026-07-12"
`;

const STOCKS_CSV = `"CUSIP","Ticker","Company","Industry"
"36262G101","GXO","GXO Logistics Inc","Integrated Freight & Logistics"
`;

const SECTOR_CSV = `"Sector","Industry"
"Industrials","Integrated Freight & Logistics"
`;

function mockCsvRoutes() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      const url = String(input instanceof Request ? input.url : input);
      if (url.includes("non_quarterly.csv")) {
        return new Response(NQ_CSV, { status: 200 });
      }
      if (url.includes("stocks.csv")) {
        return new Response(STOCKS_CSV, { status: 200 });
      }
      if (url.includes("sector_hierarchy.csv")) {
        return new Response(SECTOR_CSV, { status: 200 });
      }
      return new Response("", { status: 404 });
    }),
  );
}

describe("getNonQuarterlyFilings company resolution", () => {
  beforeEach(() => {
    clearCache();
    mockCsvRoutes();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearCache();
  });

  it("prefers the canonical stocks.csv name over the as-filed one", async () => {
    const filings = await getNonQuarterlyFilings();
    const gxo = filings.find((f) => f.ticker === "GXO");
    expect(gxo?.company).toBe("GXO Logistics Inc");
  });

  it("falls back to the as-filed name when the CUSIP is not tracked", async () => {
    const filings = await getNonQuarterlyFilings();
    const untracked = filings.find((f) => f.ticker === "ZZZ");
    expect(untracked?.company).toBe("Untracked Holdings, Inc. Common Stock");
  });

  it("keeps every filing row", async () => {
    const filings = await getNonQuarterlyFilings();
    expect(filings).toHaveLength(2);
  });
});
