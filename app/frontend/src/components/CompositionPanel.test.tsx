import { beforeAll, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";

// The treemap measures itself; jsdom ships no ResizeObserver.
beforeAll(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});

vi.mock("@/hooks/useAvailableQuarters", () => ({
  useAvailableQuarters: () => ({
    quarters: ["2026Q1"],
    latestQuarter: "2026Q1",
    isLoading: false,
  }),
}));

const STOCKS = [
  { cusip: "1", ticker: "AAA", company: "Aaa Inc", sector: "Technology" },
  { cusip: "2", ticker: "BBB", company: "Bbb Inc", sector: "Technology" },
  { cusip: "3", ticker: "CCC", company: "Ccc Inc", sector: "Healthcare" },
];

vi.mock("@/lib/dataService", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/dataService")>()),
  getStocks: () => Promise.resolve(STOCKS),
  getQuarterFundList: () => Promise.resolve(["fund"]),
  runQuarterAnalysis: () => Promise.resolve([]),
}));

const HOLDINGS = [
  { ticker: "AAA", company: "Aaa Inc", weight: 0.5, deltaPct: 10, isNew: false },
  { ticker: "BBB", company: "Bbb Inc", weight: 0.3, deltaPct: -4, isNew: false },
  { ticker: "CCC", company: "Ccc Inc", weight: 0.2, deltaPct: 0, isNew: false },
];

vi.mock("@/lib/strategyScreen", () => ({
  selectStrategyScreen: () => HOLDINGS,
  selectSmartScoreScreen: () => HOLDINGS,
}));

const { default: CompositionPanel } = await import("./CompositionPanel");

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <CompositionPanel strategyId="big_bets" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Treemap tiles carry the item name as their accessible name. */
function tile(name: string): HTMLElement {
  return screen.getByRole("button", { name });
}

const opacityOf = (name: string) => (tile(name) as HTMLElement).style.opacity;

describe("CompositionPanel sector filter", () => {
  it("dims the stocks outside the selected sector and marks the sector tile", async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.queryAllByRole("button", { name: "Technology" }).length).toBe(1),
    );

    expect(tile("Technology").getAttribute("aria-pressed")).toBe("false");
    expect(opacityOf("CCC")).toBe("1");

    fireEvent.click(tile("Technology"));

    expect(tile("Technology").getAttribute("aria-pressed")).toBe("true");
    expect(tile("Technology").style.boxShadow).toContain("--primary");
    expect(opacityOf("AAA")).toBe("1");
    expect(opacityOf("BBB")).toBe("1");
    expect(opacityOf("CCC")).toBe("0.25");
    expect(screen.getByRole("status").textContent).toBe("Showing 2 stocks in Technology");
  });

  it("toggles off when the same sector is clicked again", async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.queryAllByRole("button", { name: "Technology" }).length).toBe(1),
    );

    fireEvent.click(tile("Technology"));
    fireEvent.click(tile("Technology"));

    expect(tile("Technology").getAttribute("aria-pressed")).toBe("false");
    expect(opacityOf("CCC")).toBe("1");
    expect(screen.getByRole("status").textContent).toBe("");
  });

  it("clears on Escape and from the header button", async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.queryAllByRole("button", { name: "Technology" }).length).toBe(1),
    );

    fireEvent.click(tile("Technology"));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(opacityOf("CCC")).toBe("1");

    fireEvent.click(tile("Healthcare"));
    fireEvent.click(screen.getByRole("button", { name: /clear healthcare/i }));
    expect(opacityOf("AAA")).toBe("1");
    expect(screen.queryByRole("button", { name: /^clear/i })).toBeNull();
  });

  it("keeps a dimmed stock tile clickable", async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.queryAllByRole("button", { name: "Technology" }).length).toBe(1),
    );

    fireEvent.click(tile("Technology"));
    fireEvent.click(tile("CCC"));
    expect(tile("CCC")).toBeTruthy();
  });
});
