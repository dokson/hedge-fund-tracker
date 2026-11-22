import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ResearchProvider } from "@/components/ResearchProvider";
import type { HedgeFund, QuarterlyHolding, RawFundPerformanceRow } from "@/lib/data/types";
import type { Quarter } from "@/lib/quarters";

function rows(fund: string, returns: number[], unpriced = 0): RawFundPerformanceRow[] {
  return ["2025Q2", "2025Q3"].map((quarter, i) => ({
    fund,
    quarter,
    fund_return: String(returns[i] ?? 0),
    benchmark_return: "0.05",
    fund_cum_return: "",
    benchmark_cum_return: "",
    unpriced_weight: String(unpriced),
  }));
}

vi.mock("@/lib/dataService", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/dataService")>()),
  getHedgeFunds: vi.fn<() => Promise<HedgeFund[]>>(async () => [
    {
      cik: "1",
      fund: "Steady",
      manager: "Jane Doe",
      denomination: "Steady Capital LP",
      ciks: "",
      url: "",
    },
  ]),
  getFundPerformanceRows: vi.fn<() => Promise<RawFundPerformanceRow[]>>(async () => [
    ...rows("Steady", [0.1, 0.1]),
    ...rows("Rocket", [0.9, -0.2], 0.3),
    ...rows("Partial", [0.5]).slice(0, 1),
  ]),
  getAvailableQuarters: vi.fn<() => Promise<readonly Quarter[]>>(async () => ["2025Q1", "2025Q2"]),
  getQuarterFundList: vi.fn<(quarter: string) => Promise<string[]>>(async (quarter: string) =>
    quarter === "2025Q1" ? ["Steady", "Rocket"] : ["Steady"],
  ),
  getFundQuarterlyHoldings: vi.fn<(quarter: string) => Promise<QuarterlyHolding[]>>(
    async (quarter: string) => [
      {
        cusip: "000000001",
        ticker: "AAA",
        company: "Alpha",
        shares: 10,
        deltaShares: 0,
        value: quarter === "2025Q2" ? "2.00M" : "1.00M",
        deltaValue: "0",
        delta: "0%",
        portfolioPct: 100,
      },
    ],
  ),
}));

/** Render the phone layout deterministically in jsdom. */
function phoneViewport() {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

afterEach(() => vi.unstubAllGlobals());

import FundRanking from "./FundRanking";
import { fundPath } from "@/lib/routes";

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <TooltipProvider>
        <MemoryRouter initialEntries={["/ranking"]}>
          <ResearchProvider>
            <FundRanking />
          </ResearchProvider>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

function tableFunds(): string[] {
  const table = screen.getByRole("table", { name: /fund ranking/i });
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((r) => within(r).getAllByRole("link")[0]?.getAttribute("aria-label") ?? "");
}

/** A sortable header of the desktop table (the phone cards carry their own sort bar). */
function header(name: string): HTMLElement {
  const table = screen.getByRole("table", { name: /fund ranking/i });
  return within(table).getByRole("button", { name });
}

function cardFunds(): string[] {
  const cards = screen.getByRole("list", { name: /fund ranking cards/i });
  return within(cards)
    .getAllByRole("listitem")
    .map((li) => within(li).getAllByRole("link")[0]?.getAttribute("aria-label") ?? "");
}

describe("FundRanking page", () => {
  it("ranks the funds by cumulative return when that column is pressed, each linking to its page", async () => {
    renderPage();
    await screen.findByRole("table", { name: /fund ranking/i });
    fireEvent.click(header("Cumulative"));
    expect(tableFunds()).toEqual(["Rocket", "Partial", "Steady"]);
    const table = screen.getByRole("table", { name: /fund ranking/i });
    expect(within(table).getByRole("link", { name: "Steady" }).getAttribute("href")).toBe(
      fundPath("Steady"),
    );
  });

  it("ranks the Risk tab by consistency, then re-sorts on a header in it", async () => {
    renderPage();
    await screen.findByRole("table", { name: /fund ranking/i });
    fireEvent.click(header("Cumulative"));
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Risk" }), {
      button: 0,
    });
    const table = await screen.findByRole("table", { name: /fund ranking/i });
    // Only Rocket's lead varies, so it alone has a consistency; the others rank after it.
    expect(tableFunds()[0]).toBe("Rocket");
    expect(
      within(table)
        .getByRole("columnheader", { name: /consistency/i })
        .getAttribute("aria-sort"),
    ).toBe("descending");
    fireEvent.click(header("Max drawdown"));
    expect(tableFunds()).toEqual(["Partial", "Steady", "Rocket"]);
  });

  it("sorts the phone cards from their sort bar with the open tab's columns", async () => {
    phoneViewport();
    renderPage();
    await screen.findByRole("list", { name: /fund ranking cards/i });
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Risk" }), {
      button: 0,
    });
    await screen.findByRole("list", { name: /fund ranking cards/i });
    // The other tabs stay mounted (findable), hidden: only the open panel is in the a11y tree.
    expect(within(screen.getByRole("tabpanel")).getAllByText("Consistency").length).toBeGreaterThan(
      0,
    );
    const bar = within(screen.getByRole("tabpanel")).getByText("Sort").parentElement!;
    // The Risk tab's sortable columns, by their short card labels.
    expect(
      within(bar)
        .getByRole("button", { name: /Consist/ })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    fireEvent.click(within(bar).getByRole("button", { name: /Drawdown/ }));
    expect(cardFunds()).toEqual(["Partial", "Steady", "Rocket"]);
  });

  it("ranks every fund and marks the ones measured on fewer quarters", async () => {
    renderPage();
    await screen.findByRole("table", { name: /fund ranking/i });
    expect(tableFunds()).toContain("Partial");
    expect(
      screen.getAllByRole("button", { name: /measured on 1 of 2 quarters/i }).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /low price coverage/i }).length).toBeGreaterThan(
      0,
    );
  });

  it("uses each fund's newest filed book for the portfolio card", async () => {
    phoneViewport();
    renderPage();
    await screen.findByRole("list", { name: /fund ranking cards/i });
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Portfolio" }), {
      button: 0,
    });
    const cards = await screen.findByRole("list", {
      name: /fund ranking cards/i,
    });
    const steady = within(cards).getByRole("link", { name: "Steady" }).closest("li")!;
    const rocket = within(cards).getByRole("link", { name: "Rocket" }).closest("li")!;
    expect(await within(steady).findByText("$2.00M")).toBeTruthy();
    expect(within(steady).getByText("AUM")).toBeTruthy();
    expect(await within(rocket).findByText("$1.00M")).toBeTruthy();
  });

  it("shows the fund identity, logo and manager in the active layout", async () => {
    renderPage();
    const table = await screen.findByRole("table", { name: /fund ranking/i });
    const link = within(table).getByRole("link", { name: "Steady" });
    expect(link.getAttribute("href")).toBe(fundPath("Steady"));
    const row = link.closest("tr")!;
    expect(await within(row).findByText("Jane Doe")).toBeTruthy();
    expect(within(row).getByText("S")).toBeTruthy();
  });

  it("shows the fund identity and featured metric on phone cards", async () => {
    phoneViewport();
    renderPage();
    const cards = await screen.findByRole("list", {
      name: /fund ranking cards/i,
    });
    const link = within(cards).getByRole("link", { name: "Steady" });
    expect(link.getAttribute("href")).toBe(fundPath("Steady"));
    const row = link.closest("li")!;
    expect(await within(row).findByText("Jane Doe")).toBeTruthy();
    expect(within(row).getByText("%/yr")).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
    // Each tab features its own ranking metric, once: Risk is ranked by Consistency, with
    // %/yr only as the shared reference.
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Risk" }), { button: 0 });
    const riskCards = within(await screen.findByRole("tabpanel")).getByRole("list", {
      name: /fund ranking cards/i,
    });
    const riskRow = within(riskCards).getByRole("link", { name: "Steady" }).closest("li")!;
    expect(within(riskRow).getAllByText("Consistency")).toHaveLength(1);
    expect(within(riskRow).getAllByText("%/yr")).toHaveLength(1);
  });
});
