import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { HedgeFund, QuarterlyHolding } from "@/lib/dataService";
import { fundPath, ROUTES } from "@/lib/routes";

const aggregateSpy = vi.hoisted(() =>
  vi.fn<(rows: QuarterlyHolding[]) => QuarterlyHolding[]>((rows) => rows),
);

vi.mock("@/lib/dataService", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/dataService")>();
  const holding: QuarterlyHolding = {
    cusip: "000000001",
    ticker: "AAA",
    company: "Alpha Co",
    shares: 10,
    deltaShares: 0,
    value: "1.00M",
    deltaValue: "0",
    delta: "0%",
    portfolioPct: 100,
  };
  return {
    ...actual,
    getHedgeFunds: vi.fn<() => Promise<HedgeFund[]>>(async () => []),
    getStocks: vi.fn<() => Promise<never[]>>(async () => []),
    getNonQuarterlyFilings: vi.fn<() => Promise<never[]>>(async () => []),
    getFundAvailableQuarters: vi.fn<() => Promise<string[]>>(async () => ["2026Q2"]),
    getFundQuarterlyHoldings: vi.fn<() => Promise<QuarterlyHolding[]>>(async () => [holding]),
    aggregateHoldingsByTicker: aggregateSpy,
  };
});

import FundPortfolio from "./FundPortfolio";

class NoopResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal("ResizeObserver", NoopResizeObserver);

function GoToFund({ name }: { name: string }) {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => void navigate(fundPath(name))}>
      go {name}
    </button>
  );
}

describe("FundPortfolio fund detail", () => {
  it("resets table state when navigating to another fund", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <TooltipProvider>
          <MemoryRouter initialEntries={[fundPath("Fund A")]}>
            <GoToFund name="Fund B" />
            <Routes>
              <Route path={`${ROUTES.funds}/:fundId`} element={<FundPortfolio />} />
            </Routes>
          </MemoryRouter>
        </TooltipProvider>
      </QueryClientProvider>,
    );
    const header = async () =>
      (await screen.findAllByRole("columnheader")).find((th) => th.textContent?.includes("Port %"));
    const before = await header();
    expect(before?.getAttribute("aria-sort")).toBe("descending");
    const sortButton = before?.querySelector("button");
    if (sortButton) fireEvent.click(sortButton);
    expect((await header())?.getAttribute("aria-sort")).toBe("ascending");

    fireEvent.click(screen.getByRole("button", { name: "go Fund B" }));
    await screen.findByRole("button", { name: "go Fund B" });
    expect((await header())?.getAttribute("aria-sort")).toBe("descending");
  });
});

describe("FundPortfolio holdings aggregation", () => {
  it("does not re-aggregate holdings on unrelated re-renders", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <TooltipProvider>
          <MemoryRouter initialEntries={[fundPath("Fund A")]}>
            <Routes>
              <Route path={`${ROUTES.funds}/:fundId`} element={<FundPortfolio />} />
            </Routes>
          </MemoryRouter>
        </TooltipProvider>
      </QueryClientProvider>,
    );
    const headers = await screen.findAllByRole("columnheader");
    const sortButton = headers
      .find((th) => th.textContent?.includes("Port %"))
      ?.querySelector("button");
    const callsBefore = aggregateSpy.mock.calls.length;
    if (sortButton) fireEvent.click(sortButton);
    if (sortButton) fireEvent.click(sortButton);
    expect(aggregateSpy.mock.calls.length).toBe(callsBefore);
  });
});
