import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchQuarterAnalysis } from "../dataService";

function mockAnalysisFetch(rows: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(rows), { status: 200 })),
  );
}

const BASE_ROW = {
  Ticker: "AAA",
  Company: "Alpha Co",
  Total_Value: 1000,
  Total_Delta_Value: 1000,
  Max_Portfolio_Pct: 2,
  Avg_Portfolio_Pct: 2,
  Buyer_Count: 1,
  Seller_Count: 0,
  Holder_Count: 1,
  New_Holder_Count: 1,
  Close_Count: 0,
  High_Conviction_Count: 0,
  Net_Buyers: 1,
  Buyer_Seller_Ratio: 1,
  Ownership_Delta_Avg: 0,
  Avg_Fund_Concentration: 0,
};

describe("fetchQuarterAnalysis", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reconstructs Infinity for an all-new stock whose Delta was nulled by JSON", () => {
    // The backend serializer replaces ±Infinity with null (JSON has no inf);
    // an all-new position must come back as Infinity ("NEW"), not 0%.
    mockAnalysisFetch([{ ...BASE_ROW, Delta: null }]);
    return fetchQuarterAnalysis("2026Q2").then((rows) => {
      expect(rows?.[0].delta).toBe(Infinity);
    });
  });

  it("keeps a genuine zero delta at 0 when holders are not all new", () => {
    mockAnalysisFetch([
      { ...BASE_ROW, Delta: 0, Holder_Count: 3, New_Holder_Count: 1, Close_Count: 0 },
    ]);
    return fetchQuarterAnalysis("2026Q2").then((rows) => {
      expect(rows?.[0].delta).toBe(0);
    });
  });

  it("passes finite deltas through untouched", () => {
    mockAnalysisFetch([
      { ...BASE_ROW, Delta: 7.6, Holder_Count: 2, New_Holder_Count: 1, Close_Count: 0 },
    ]);
    return fetchQuarterAnalysis("2026Q2").then((rows) => {
      expect(rows?.[0].delta).toBeCloseTo(7.6);
    });
  });
});
