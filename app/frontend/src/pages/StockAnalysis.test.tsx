import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ResearchProvider } from "@/components/ResearchProvider";
import type { FundTickerHolding, Stock } from "@/lib/dataService";
import { ROUTES, stockPath } from "@/lib/routes";

const { useQuarterAnalysisMock } = vi.hoisted(() => ({
  useQuarterAnalysisMock: vi.fn<() => unknown>(),
}));

vi.mock("@/lib/dataService", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/dataService")>()),
  getStocks: vi.fn<() => Promise<Stock[]>>(async () => []),
  runStockAnalysis: vi.fn<() => Promise<FundTickerHolding[]>>(async () => []),
}));

vi.mock("@/hooks/useAvailableQuarters", () => ({
  useAvailableQuarters: () => ({ quarters: ["2026Q2"], latestQuarter: "2026Q2", isLoading: false }),
}));

vi.mock("@/hooks/useQuarterAnalysis", () => ({
  useQuarterAnalysis: useQuarterAnalysisMock,
}));

vi.mock("@/components/StockPriceChart", () => ({ StockPriceChart: () => null }));

import StockAnalysis from "./StockAnalysis";

describe("StockAnalysis smart score", () => {
  it("shows the quarter-analysis error in place of the smart score panel", async () => {
    useQuarterAnalysisMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("Failed to fetch analysis: 503"),
    });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <TooltipProvider>
          <MemoryRouter initialEntries={[stockPath("AAA")]}>
            <ResearchProvider>
              <Routes>
                <Route path={`${ROUTES.stock}/:ticker`} element={<StockAnalysis />} />
              </Routes>
            </ResearchProvider>
          </MemoryRouter>
        </TooltipProvider>
      </QueryClientProvider>,
    );
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Failed to fetch analysis: 503");
  });

  it("shows the composite score once, in its explanation panel rather than the identity header", async () => {
    useQuarterAnalysisMock.mockReturnValue({
      data: [
        {
          ticker: "AAA",
          smartScore: 8.6,
          scoreBreadth: 51,
          scoreMomentum: 78,
          scoreConviction: 89,
        },
      ],
      isLoading: false,
      isError: false,
      error: null,
    });

    render(
      <QueryClientProvider client={new QueryClient()}>
        <TooltipProvider>
          <MemoryRouter initialEntries={[stockPath("AAA")]}>
            <ResearchProvider>
              <Routes>
                <Route path={`${ROUTES.stock}/:ticker`} element={<StockAnalysis />} />
              </Routes>
            </ResearchProvider>
          </MemoryRouter>
        </TooltipProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Smart Score" })).toBeTruthy();
    expect(
      screen.getAllByTitle(
        "Smart Score: relative institutional screen (1–10), not a return forecast",
      ),
    ).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Add to starred" })).toBeTruthy();
  });
});
