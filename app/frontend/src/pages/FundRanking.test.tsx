import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { HedgeFund, RawFundPerformanceRow } from "@/lib/data/types";

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
}));

import FundRanking from "./FundRanking";
import { RANKING_PAGE } from "@/lib/pageMeta";
import { fundPath } from "@/lib/routes";

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <TooltipProvider>
        <MemoryRouter initialEntries={["/ranking"]}>
          <FundRanking />
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
    .map((r) => within(r).getAllByRole("link")[0]?.textContent ?? "");
}

describe("FundRanking page", () => {
  it("ranks the funds by cumulative return, each linking to its page", async () => {
    renderPage();
    await screen.findByRole("table", { name: /fund ranking/i });
    expect(tableFunds()).toEqual(["Rocket", "Partial", "Steady"]);
    const table = screen.getByRole("table", { name: /fund ranking/i });
    expect(within(table).getByRole("link", { name: "Steady" }).getAttribute("href")).toBe(
      fundPath("Steady"),
    );
  });

  it("re-sorts when a column header is pressed", async () => {
    renderPage();
    await screen.findByRole("table", { name: /fund ranking/i });
    fireEvent.click(screen.getByRole("button", { name: "Worst quarter" }));
    expect(tableFunds()).toEqual(["Partial", "Steady", "Rocket"]);
  });

  it("ranks every fund and marks the ones measured on fewer quarters", async () => {
    renderPage();
    await screen.findByRole("table", { name: /fund ranking/i });
    expect(tableFunds()).toContain("Partial");
    expect(screen.getAllByLabelText(/measured on 1 of 2 quarters/i).length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText(/low price coverage/i).length).toBeGreaterThan(0);
  });

  it("shows each fund with its logo and manager, as elsewhere on the site", async () => {
    renderPage();
    const table = await screen.findByRole("table", { name: /fund ranking/i });
    const row = within(table).getByRole("link", { name: "Steady" }).closest("tr");
    expect(row).not.toBeNull();
    if (!row) return;
    expect(await within(row).findByText("Jane Doe")).toBeTruthy();
    expect(within(row).getByText("S")).toBeTruthy();
  });

  it("sets the page title", async () => {
    renderPage();
    await screen.findByRole("table", { name: /fund ranking/i });
    expect(document.title).toBe(RANKING_PAGE.title);
  });
});
