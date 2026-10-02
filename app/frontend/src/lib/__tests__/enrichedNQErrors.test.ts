import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const holdingsMock = vi.hoisted(() =>
  vi.fn<(quarter: string, fund: string) => Promise<unknown[]>>(),
);

vi.mock("../data/quarterData", () => ({
  getFundAvailableQuarters: vi.fn<() => Promise<string[]>>(async () => ["2026Q2"]),
  getFundQuarterlyHoldings: holdingsMock,
}));

vi.mock("../data/stocks", () => ({ getStocks: vi.fn<() => Promise<unknown[]>>(async () => []) }));

import { clearCache } from "../data/fetch";
import { getEnrichedNQFilings } from "../data/nonQuarterly";

const NQ_CSV = `"Fund","CUSIP","Ticker","Company","Shares","Value","Avg_Price","Date","Filing_Date"
"Fund A","000000001","AAA","Alpha","100","1.00M","10.00","2026-07-14","2026-07-21"
`;

describe("getEnrichedNQFilings per-fund load failures", () => {
  beforeEach(() => {
    clearCache();
    vi.stubGlobal(
      "fetch",
      vi.fn<() => Promise<Response>>(async () => new Response(NQ_CSV, { status: 200 })),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearCache();
    holdingsMock.mockReset();
  });

  it("propagates the error instead of reporting the position as NEW", async () => {
    holdingsMock.mockRejectedValue(new Error("network down"));
    await expect(getEnrichedNQFilings()).rejects.toThrow("network down");
  });

  it("does not cache the failed result, so a retry recovers", async () => {
    holdingsMock.mockRejectedValueOnce(new Error("network down"));
    await expect(getEnrichedNQFilings()).rejects.toThrow("network down");
    holdingsMock.mockResolvedValueOnce([
      { cusip: "000000001", ticker: "AAA", shares: 50, portfolioPct: 1, value: "0.5M" },
    ]);
    const rows = await getEnrichedNQFilings();
    expect(rows[0]?.deltaType).toBe("INCREASE");
  });
});
