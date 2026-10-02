import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { FundTickerHolding, Stock } from "@/lib/dataService";
import { ROUTES, stockPath } from "@/lib/routes";

vi.mock("@/lib/dataService", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/dataService")>()),
  getStocks: vi.fn<() => Promise<Stock[]>>(async () => []),
  runStockAnalysis: vi.fn<() => Promise<FundTickerHolding[]>>(async () => []),
}));

vi.mock("@/hooks/useAvailableQuarters", () => ({
  useAvailableQuarters: () => ({ quarters: ["2026Q2"], latestQuarter: "2026Q2", isLoading: false }),
}));

vi.mock("@/hooks/useQuarterAnalysis", () => ({
  useQuarterAnalysis: () => ({
    data: undefined,
    isLoading: false,
    isError: true,
    error: new Error("Failed to fetch analysis: 503"),
  }),
}));

vi.mock("@/components/StockPriceChart", () => ({ StockPriceChart: () => null }));

import StockAnalysis from "./StockAnalysis";

describe("StockAnalysis smart score", () => {
  it("shows the quarter-analysis error in place of the smart score panel", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <TooltipProvider>
          <MemoryRouter initialEntries={[stockPath("AAA")]}>
            <Routes>
              <Route path={`${ROUTES.stock}/:ticker`} element={<StockAnalysis />} />
            </Routes>
          </MemoryRouter>
        </TooltipProvider>
      </QueryClientProvider>,
    );
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Failed to fetch analysis: 503");
  });
});
