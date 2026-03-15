import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { runQuarterAnalysis, clearCache } from "../dataService";

const MOCK_STOCKS_CSV = `CUSIP,Ticker,Company,Sector
A123456,TSLA,Tesla Inc,Consumer Discretionary
B654321,AAPL,Apple Inc,Information Technology
C111111,MSFT,Microsoft Corp,Information Technology`;

const MOCK_FUND_A_CSV = `CUSIP,Ticker,Company,Shares,Delta_Shares,Value,Delta_Value,Delta,Portfolio%
A123456,TSLA,Tesla Inc,1000,1000,"$2.5M","$2.5M",NEW,5.0
B654321,AAPL,Apple Inc,2000,500,"$4M","$1M",25.0,8.0
C111111,MSFT,Microsoft Corp,0,-500,"$0","-$1.5M",-100.0,0`;

const MOCK_FUND_B_CSV = `CUSIP,Ticker,Company,Shares,Delta_Shares,Value,Delta_Value,Delta,Portfolio%
A123456,TSLA,Tesla Inc,500,200,"$1.25M","$500K",40.0,3.0
B654321,AAPL,Apple Inc,3000,0,"$6M","$0",0.0,12.0`;

function mockFetch(url: string, init?: RequestInit): Promise<Response> {
  const headers = { ok: true, status: 200 } as Record<string, unknown>;

  const urlStr = typeof url === "string" ? url : "";

  if (urlStr.includes("stocks.csv")) {
    return Promise.resolve(new Response(MOCK_STOCKS_CSV, { headers: { "Content-Type": "text/csv" } }));
  }
  if (urlStr.includes("/api/database/quarters/")) {
    return Promise.resolve(new Response(JSON.stringify(["fund_A.csv", "fund_B.csv"]), {
      headers: { "Content-Type": "application/json" },
    }));
  }
  if (urlStr.includes("fund_A.csv") || urlStr.includes("Fund%20A.csv")) {
    return Promise.resolve(new Response(MOCK_FUND_A_CSV, { headers: { "Content-Type": "text/csv" } }));
  }
  if (urlStr.includes("fund_B.csv") || urlStr.includes("Fund%20B.csv")) {
    return Promise.resolve(new Response(MOCK_FUND_B_CSV, { headers: { "Content-Type": "text/csv" } }));
  }

  return Promise.reject(new Error(`Unmocked URL: ${urlStr}`));
}

describe("runQuarterAnalysis", () => {
  beforeEach(() => {
    clearCache();
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should identify new positions where all shares are delta", async () => {
    const results = await runQuarterAnalysis("2025Q1");

    const tsla = results.find((r) => r.ticker === "TSLA");
    expect(tsla).toBeDefined();

    // Fund A TSLA: shares=1000, deltaShares=1000 → NEW
    expect(tsla!.newHolderCount).toBeGreaterThanOrEqual(1);
  });

  it("should identify closed positions where shares are zero", async () => {
    const results = await runQuarterAnalysis("2025Q1");

    const msft = results.find((r) => r.ticker === "MSFT");
    expect(msft).toBeDefined();

    // Fund A MSFT: shares=0 → closed
    expect(msft!.closeCount).toBe(1);
  });

  it("should compute total value across all funds for a ticker", async () => {
    const results = await runQuarterAnalysis("2025Q1");

    const aapl = results.find((r) => r.ticker === "AAPL");
    expect(aapl).toBeDefined();

    // Fund A: $4M, Fund B: $6M → total $10M
    expect(aapl!.totalValue).toBeCloseTo(10_000_000, -3);
  });

  it("should compute net buyers as buyerCount minus sellerCount", async () => {
    const results = await runQuarterAnalysis("2025Q1");

    const tsla = results.find((r) => r.ticker === "TSLA");
    expect(tsla).toBeDefined();

    // Both funds have positive delta for TSLA → netBuyers = 2
    expect(tsla!.netBuyers).toBe(2);
  });

  it("should compute total delta value across all funds", async () => {
    const results = await runQuarterAnalysis("2025Q1");

    const tsla = results.find((r) => r.ticker === "TSLA");
    expect(tsla).toBeDefined();

    // Fund A: +$2.5M, Fund B: +$500K → total +$3M
    expect(tsla!.totalDeltaValue).toBeCloseTo(3_000_000, -3);
  });

  it("should set holderCount to 0 for fully closed positions", async () => {
    const results = await runQuarterAnalysis("2025Q1");

    const msft = results.find((r) => r.ticker === "MSFT");
    expect(msft).toBeDefined();

    // Only Fund A held MSFT and closed it → no holders remain
    expect(msft!.holderCount).toBe(0);
  });
});
