import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import { ResearchProvider } from "@/components/ResearchProvider";
import type { EnrichedNQFiling } from "@/lib/data/types";
import type * as DataService from "@/lib/dataService";
import { ROUTES } from "@/lib/routes";

vi.mock("@/lib/dataService", async (importOriginal) => ({
  ...(await importOriginal<typeof DataService>()),
  getStocks: vi.fn<typeof DataService.getStocks>(async () => []),
  getHedgeFunds: vi.fn<typeof DataService.getHedgeFunds>(async () => []),
}));

vi.mock("@/hooks/useEnrichedNQFilings", () => ({
  useEnrichedNQFilings: () => ({
    data: [
      filing("RECENT", "2026-10-25", "2026-10-26"),
      filing("LATE", "2026-09-15", "2026-10-30"),
      filing("OLD", "2026-09-10", "2026-09-20"),
    ],
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

import Dashboard from "./Dashboard";

function filing(ticker: string, date: string, filingDate: string): EnrichedNQFiling {
  return {
    fund: "Example",
    cusip: ticker,
    ticker,
    company: `${ticker} Company`,
    shares: 120,
    value: "1.2K",
    avgPrice: "10.00",
    date,
    filingDate,
    quarterShares: 100,
    deltaShares: 20,
    deltaType: "INCREASE",
    deltaPct: 20,
    quarterPortfolioPct: 1,
    estimatedPortfolioPct: null,
  };
}

function tableTickers(): string[] {
  const table = screen.getByRole("table", { name: /latest filings/i });
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("link")[0]?.textContent ?? "");
}

describe("Latest Filings publication window", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-01T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("includes late-published positions and orders by publication rather than position date", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <TooltipProvider>
          <MemoryRouter initialEntries={[ROUTES.latest]}>
            <ResearchProvider>
              <Dashboard />
            </ResearchProvider>
          </MemoryRouter>
        </TooltipProvider>
      </QueryClientProvider>,
    );
    await screen.findByRole("table", { name: /latest filings/i });
    expect(tableTickers()).toEqual(["LATE", "RECENT"]);
    fireEvent.click(screen.getByRole("radio", { name: "All" }));
    expect(tableTickers()).toEqual(["LATE", "RECENT", "OLD"]);
  });
});
