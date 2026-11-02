import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ResearchProvider } from "@/components/ResearchProvider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useQuarterAnalysis } from "@/hooks/useQuarterAnalysis";
import type { StockQuarterAnalysis } from "@/lib/data/types";
import type * as DataService from "@/lib/dataService";
import { ROUTES } from "@/lib/routes";
import { STRATEGY_BY_TAB } from "@/lib/strategies";

vi.mock("@/lib/dataService", async (importOriginal) => ({
  ...(await importOriginal<typeof DataService>()),
  getHedgeFunds: vi.fn<typeof DataService.getHedgeFunds>(async () => []),
  getQuarterFundList: vi.fn<typeof DataService.getQuarterFundList>(async () => []),
}));

vi.mock("@/hooks/useAvailableQuarters", () => ({
  useAvailableQuarters: () => ({
    quarters: ["2026Q1", "2026Q2"],
    latestQuarter: "2026Q2",
    isLoading: false,
  }),
}));

vi.mock("@/hooks/useQuarterAnalysis", () => ({
  useQuarterAnalysis: vi.fn<() => unknown>(() => ({
    data: [
      stock("AMZN", 58, 10),
      stock("TSM", 42, 9.9, {
        netBuyers: 5,
        newHolderCount: 3,
        avgPortfolioPct: 3,
        maxPortfolioPct: 7,
        delta: 20,
      }),
      stock("STX", 35, 9.8, {
        netBuyers: 1,
        newHolderCount: 2,
        maxPortfolioPct: 10,
        totalDeltaValue: -100,
        delta: -10,
      }),
    ],
    isLoading: false,
    isError: false,
  })),
}));

import QuarterlyTrends from "./QuarterlyTrends";

function stock(
  ticker: string,
  holderCount: number,
  smartScore: number,
  overrides: Partial<StockQuarterAnalysis> = {},
): StockQuarterAnalysis {
  return {
    ticker,
    company: `${ticker} Company`,
    totalValue: 1000,
    totalDeltaValue: 100,
    maxPortfolioPct: 5,
    avgPortfolioPct: 2,
    buyerCount: 5,
    sellerCount: 2,
    holderCount,
    newHolderCount: 1,
    closeCount: 0,
    highConvictionCount: 1,
    netBuyers: 3,
    buyerSellerRatio: 2.5,
    ownershipDeltaAvg: 10,
    fundConcentrationAvg: 1,
    delta: 10,
    smartScore,
    ...overrides,
  };
}

function Detail() {
  const navigate = useNavigate();
  return <button onClick={() => void navigate(-1)}>Back to research</button>;
}

function renderResearch(initialEntry: string = ROUTES.quarterly) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[initialEntry]}>
          <ResearchProvider>
            <Routes>
              <Route path={ROUTES.quarterly} element={<QuarterlyTrends />} />
              <Route path={`${ROUTES.stock}/:ticker`} element={<Detail />} />
            </Routes>
          </ResearchProvider>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

function tickers(): string[] {
  return within(screen.getByRole("table", { name: "Ranked stocks" }))
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("link")[0]?.textContent ?? "");
}

describe("Quarterly research context", () => {
  beforeEach(() => {
    localStorage.removeItem("starred_stock");
    localStorage.removeItem("starred_fund");
    vi.mocked(useQuarterAnalysis).mockClear();
  });

  it("restores filters and a custom sort after returning from a stock", async () => {
    renderResearch();
    const table = await screen.findByRole("table", { name: "Ranked stocks" });
    fireEvent.change(screen.getByRole("spinbutton", { name: "Min Holders" }), {
      target: { value: "40" },
    });
    fireEvent.click(within(table).getByRole("button", { name: "Holders" }));
    fireEvent.click(within(table).getByRole("button", { name: "Holders" }));
    expect(tickers()).toEqual(["TSM", "AMZN"]);
    fireEvent.click(within(table).getByRole("link", { name: "AMZN" }));
    fireEvent.click(await screen.findByRole("button", { name: "Back to research" }));
    await screen.findByRole("table", { name: "Ranked stocks" });
    expect(
      (screen.getByRole("spinbutton", { name: "Min Holders" }) as HTMLInputElement).value,
    ).toBe("40");
    expect(tickers()).toEqual(["TSM", "AMZN"]);
    expect(screen.getByText("Sorted by Holders · ascending")).toBeTruthy();
  });

  it("keeps each research question's filters separate", async () => {
    renderResearch();
    await screen.findByRole("table", { name: "Ranked stocks" });
    fireEvent.change(screen.getByRole("spinbutton", { name: "Min Holders" }), {
      target: { value: "40" },
    });
    fireEvent.keyDown(screen.getByRole("tab", { name: "Consensus Buys" }), { key: "Enter" });
    expect(
      (screen.getByRole("spinbutton", { name: "Min Holders" }) as HTMLInputElement).value,
    ).toBe("0");
    fireEvent.keyDown(screen.getByRole("tab", { name: "Smart Score" }), { key: "Enter" });
    expect(
      (screen.getByRole("spinbutton", { name: "Min Holders" }) as HTMLInputElement).value,
    ).toBe("40");
  });

  it("restores the strategy ranking without resetting research filters", async () => {
    renderResearch();
    const table = await screen.findByRole("table", { name: "Ranked stocks" });
    expect(screen.queryByRole("button", { name: "Restore default ranking" })).toBeNull();
    fireEvent.change(screen.getByRole("spinbutton", { name: "Min Holders" }), {
      target: { value: "40" },
    });
    fireEvent.click(within(table).getByRole("button", { name: "Holders" }));
    fireEvent.click(within(table).getByRole("button", { name: "Holders" }));
    const firstCard = within(screen.getByRole("list", { name: "Ranked stocks" })).getAllByRole(
      "listitem",
    )[0];
    expect(within(firstCard).getByText("Holders").nextElementSibling?.textContent).toBe("42");
    expect(screen.getByText("Sorted by Holders · ascending")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Restore default ranking" }));
    expect(tickers()).toEqual(["AMZN", "TSM"]);
    expect(
      (screen.getByRole("spinbutton", { name: "Min Holders" }) as HTMLInputElement).value,
    ).toBe("40");
    expect(screen.queryByText(/Sorted by/)).toBeNull();
    const restoredCard = within(screen.getByRole("list", { name: "Ranked stocks" })).getAllByRole(
      "listitem",
    )[0];
    expect(within(restoredCard).getByText("Smart Score")).toBeTruthy();
    expect(within(restoredCard).getByText("10.0")).toBeTruthy();
  });

  it.each<[string, string[], string]>([
    ["smartscore", ["AMZN", "TSM", "STX"], "Smart Score"],
    ["consensus", ["TSM", "AMZN", "STX"], "Net Buyers"],
    ["new", ["TSM", "STX", "AMZN"], "New Holders"],
    ["bigbets", ["STX", "TSM", "AMZN"], "Max Ptf %"],
    ["avgportfolio", ["TSM", "AMZN", "STX"], "Avg Ptf %"],
    ["increasing", ["TSM", "AMZN"], "Aggregate Δ %"],
    ["decreasing", ["STX"], "Position Δ $"],
  ])(
    "keeps the %s question, default ranking and labeled mobile headline",
    async (tab, expected, metric) => {
      renderResearch(`${ROUTES.quarterly}?tab=${tab}`);
      const table = await screen.findByRole("table", { name: "Ranked stocks" });
      expect(screen.getAllByRole("tab")).toHaveLength(7);
      expect(tickers()).toEqual(expected);
      const strategy = STRATEGY_BY_TAB[tab];
      expect(screen.getByTitle(strategy.description).textContent).toBeTruthy();
      expect(
        within(table)
          .getByRole("button", { name: metric })
          .closest("th")
          ?.getAttribute("aria-sort"),
      ).toBe(strategy.ascending ? "ascending" : "descending");
      expect(screen.getByRole("switch", { name: "Exclude NEW" }).getAttribute("aria-checked")).toBe(
        String(strategy.excludeInfiniteDelta),
      );
      const firstCard = within(screen.getByRole("list", { name: "Ranked stocks" })).getAllByRole(
        "listitem",
      )[0];
      expect(within(firstCard).getByText(metric)).toBeTruthy();
      expect(screen.queryByRole("button", { name: "Restore default ranking" })).toBeNull();
    },
  );

  it("filters starred stocks locally but requests fresh analysis for starred funds", async () => {
    localStorage.setItem("starred_stock", JSON.stringify(["TSM"]));
    localStorage.setItem("starred_fund", JSON.stringify(["Lingotto"]));
    renderResearch();
    await screen.findByRole("table", { name: "Ranked stocks" });
    fireEvent.click(screen.getByRole("button", { name: /Stocks 1/ }));
    expect(tickers()).toEqual(["TSM"]);
    expect(vi.mocked(useQuarterAnalysis).mock.lastCall?.[1]?.fundFilter).toBeUndefined();
    fireEvent.click(screen.getByRole("button", { name: /Funds 1/ }));
    expect(vi.mocked(useQuarterAnalysis).mock.lastCall?.[1]?.fundFilter).toEqual(
      new Set(["Lingotto"]),
    );
    fireEvent.click(screen.getByRole("button", { name: /Stocks 1/ }));
    expect(tickers()).toEqual(["AMZN", "TSM", "STX"]);
  });
});
