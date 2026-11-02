import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ResearchProvider } from "@/components/ResearchProvider";
import type { Stock, StockQuarterAnalysis } from "@/lib/dataService";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import type { ReactNode } from "react";

vi.mock("@/lib/dataService", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/dataService")>()),
  getStocks: vi.fn<() => Promise<Stock[]>>(async () => [
    { cusip: "000000001", ticker: "AAA", company: "Alpha Co" },
  ]),
  getSectorHierarchy: vi.fn<() => Promise<never[]>>(async () => []),
}));

vi.mock("@/hooks/useAvailableQuarters", () => ({
  useAvailableQuarters: vi.fn<
    () => { quarters: string[]; latestQuarter: string | undefined; isLoading: boolean }
  >(() => ({ quarters: [], latestQuarter: undefined, isLoading: false })),
}));

// jsdom has no list viewport; exercise the page's readiness boundary with all fixture rows.
vi.mock("@/components/ui/VirtualList", () => ({
  VirtualList: ({
    items,
    renderItem,
  }: {
    items: StockQuarterAnalysis[];
    renderItem: (stock: StockQuarterAnalysis, index: number) => ReactNode;
  }) => (
    <div>
      {items.map((stock, index) => (
        <div key={stock.ticker}>{renderItem(stock, index)}</div>
      ))}
    </div>
  ),
}));

import StockBrowser from "./StockBrowser";
import { stockPath, stocksByIndustry } from "@/lib/routes";

function LocationProbe() {
  return <span data-testid="location-search">{useLocation().search}</span>;
}

function renderAt(path: string, client = new QueryClient()) {
  return render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[path]}>
          <ResearchProvider>
            <StockBrowser />
            <LocationProbe />
          </ResearchProvider>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(useAvailableQuarters).mockReturnValue({
    quarters: [],
    latestQuarter: undefined,
    isLoading: false,
  });
});

function completedAnalysis(): StockQuarterAnalysis {
  return {
    ticker: "ZZZ",
    company: "Zeta Co",
    totalValue: 100_000,
    totalDeltaValue: 10_000,
    maxPortfolioPct: 10,
    avgPortfolioPct: 5,
    buyerCount: 8,
    sellerCount: 1,
    holderCount: 10,
    newHolderCount: 2,
    closeCount: 0,
    highConvictionCount: 2,
    netBuyers: 7,
    buyerSellerRatio: 8,
    ownershipDeltaAvg: 1,
    fundConcentrationAvg: 5,
    delta: 10,
    smartScore: 9.8,
    scoreBreadth: 99,
    scoreMomentum: 98,
    scoreConviction: 97,
  };
}

describe("StockBrowser analysis readiness", () => {
  it("does not render floor scores while the latest quarter is still loading", async () => {
    vi.mocked(useAvailableQuarters).mockReturnValue({
      quarters: [],
      latestQuarter: undefined,
      isLoading: true,
    });
    renderAt("/stocks?tab=score");
    expect((await screen.findByRole("status")).textContent).toContain("Loading Smart Score");
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).queryByRole("link", { name: "AAA" })).toBeNull();
    expect(within(panel).queryByText("1.0")).toBeNull();
    expect(within(panel).queryByText("0")).toBeNull();
  });

  it("replaces neutral loading rows with the completed ranking, including genuine floor scores", async () => {
    vi.mocked(useAvailableQuarters).mockReturnValue({
      quarters: ["2026Q3"],
      latestQuarter: "2026Q3",
      isLoading: false,
    });
    const client = new QueryClient();
    // Hold the real query pending without depending on timers or a network response.
    client.setQueryDefaults(["quarterAnalysis"], { enabled: false });
    renderAt("/stocks?tab=score", client);
    expect((await screen.findByRole("status")).textContent).toContain("Loading Smart Score");
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).queryByRole("link", { name: "AAA" })).toBeNull();
    expect(within(panel).queryByText("1.0")).toBeNull();
    await act(async () => {
      client.setQueryData(["quarterAnalysis", "2026Q3"], [completedAnalysis()]);
    });
    await waitFor(() =>
      expect(within(panel).getAllByRole("link", { name: "ZZZ" }).length).toBeGreaterThan(0),
    );
    expect(within(panel).queryByRole("status")).toBeNull();
    expect(within(panel).getAllByRole("link", { name: "AAA" }).length).toBeGreaterThan(0);
    expect(within(panel).getAllByText("9.8").length).toBeGreaterThan(0);
    expect(within(panel).getAllByText("1.0").length).toBeGreaterThan(0);
    const tickers = within(panel)
      .getAllByRole("link")
      .filter((link) => ["ZZZ", "AAA"].includes(link.textContent ?? ""));
    expect(tickers[0].textContent).toBe("ZZZ");
  });

  it("does not synthesize a floor-score ranking when no quarter is available", async () => {
    renderAt("/stocks?tab=score");
    expect(await screen.findByText("No quarter data available.")).not.toBeNull();
    expect(screen.queryByRole("link", { name: "AAA" })).toBeNull();
    expect(screen.queryByText("1.0")).toBeNull();
  });

  it.each([
    ["byvalue", "Loading institutional values"],
    ["sectors", "Loading sector values"],
  ])(
    "gates analysis-derived values on the %s tab before a quarter is known",
    async (tab, message) => {
      vi.mocked(useAvailableQuarters).mockReturnValue({
        quarters: [],
        latestQuarter: undefined,
        isLoading: true,
      });
      renderAt(`/stocks?tab=${tab}`);
      expect((await screen.findByRole("status")).textContent).toContain(message);
      const panel = screen.getByRole("tabpanel");
      expect(within(panel).queryByText("No data available.")).toBeNull();
      expect(within(panel).queryByText("0 stocks")).toBeNull();
      expect(within(panel).queryByText("1.0")).toBeNull();
    },
  );
});

describe("StockBrowser tab navigation", () => {
  it("keeps the selected tab in view and names every tab in the URL", async () => {
    const scrollIntoView = vi.fn<(options?: boolean | ScrollIntoViewOptions) => void>();
    const previous = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollIntoView");
    HTMLElement.prototype.scrollIntoView = scrollIntoView;
    try {
      renderAt("/stocks");
      await waitFor(() =>
        expect(screen.getByTestId("location-search").textContent).toContain("tab=score"),
      );
      fireEvent.mouseDown(screen.getByRole("tab", { name: "Alphabetical" }), { button: 0 });
      await waitFor(() =>
        expect(screen.getByTestId("location-search").textContent).toContain("tab=alphabetical"),
      );
      expect(screen.getByRole("tab", { name: "Alphabetical" }).getAttribute("aria-selected")).toBe(
        "true",
      );
      expect(scrollIntoView).toHaveBeenLastCalledWith({ block: "nearest", inline: "nearest" });
      expect(scrollIntoView.mock.instances.at(-1)).toBe(
        screen.getByRole("tab", { name: "Alphabetical" }),
      );
    } finally {
      if (previous) Object.defineProperty(HTMLElement.prototype, "scrollIntoView", previous);
      else Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
    }
  });
});

describe("StockBrowser industry deep link", () => {
  it("opens the By Value tab and consumes the industry param", async () => {
    renderAt(stocksByIndustry("Widgets"));
    await waitFor(() =>
      expect(screen.getByTestId("location-search").textContent).not.toContain("industry="),
    );
    const tab = screen.getByRole("tab", { name: /value/i });
    expect(tab.getAttribute("aria-selected")).toBe("true");
  });
});

describe("StockBrowser cards", () => {
  it("navigate through a real link instead of a clickable div", async () => {
    renderAt("/stocks?tab=alphabetical");
    const panel = await screen.findByRole("tabpanel");
    const link = await within(panel).findByRole("link", { name: /AAA/ });
    expect(link.getAttribute("href")).toBe(stockPath("AAA"));
    expect(panel.querySelector('[role="button"]')).toBeNull();
  });

  it("put the company tooltip on the link, since its overlay covers the card", async () => {
    renderAt("/stocks?tab=alphabetical");
    const panel = await screen.findByRole("tabpanel");
    const link = await within(panel).findByRole("link", { name: /AAA/ });
    expect(link.getAttribute("title")).toBe("Alpha Co");
  });
});
