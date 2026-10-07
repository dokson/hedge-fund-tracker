import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { parseFundPerformance, type FundPerformance } from "@/lib/dataService";

const getFundPerformance = vi.hoisted(() =>
  vi.fn<(fund: string) => Promise<FundPerformance | null>>(),
);

vi.mock("@/lib/dataService", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/dataService")>()),
  getFundPerformance,
}));

import FundPerformancePanel from "./FundPerformancePanel";

class NoopResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal("ResizeObserver", NoopResizeObserver);

function renderPanel(fund = "Alpha") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <FundPerformancePanel fund={fund} />
    </QueryClientProvider>,
  );
}

const PERF = parseFundPerformance(
  [
    {
      fund: "Alpha",
      quarter: "2026Q1",
      fund_return: "0.1",
      benchmark_return: "0.05",
      fund_cum_return: "0.1",
      benchmark_cum_return: "0.05",
      unpriced_weight: "0",
    },
    {
      fund: "Alpha",
      quarter: "2026Q2",
      fund_return: "-0.02",
      benchmark_return: "0.01",
      fund_cum_return: "0.078",
      benchmark_cum_return: "0.061",
      unpriced_weight: "0.08",
    },
  ],
  "Alpha",
);

describe("FundPerformancePanel", () => {
  it("summarises the fund's cumulative return against the S&P 500", async () => {
    getFundPerformance.mockResolvedValue(PERF);
    renderPanel();

    expect(await screen.findByRole("heading", { name: "Estimated return" })).toBeTruthy();
    expect(screen.getByText("+7.8%")).toBeTruthy();
    expect(screen.getByText("+6.1%")).toBeTruthy();
    expect(screen.getByText("+1.7 pp")).toBeTruthy();
    expect(screen.getByText("1 of 2")).toBeTruthy();
  });

  it("flags a quarter where over 5% of the book could not be priced", async () => {
    getFundPerformance.mockResolvedValue(PERF);
    renderPanel();
    expect(
      await screen.findByText(/2026 Q2: over 5% of the book could not be priced/i),
    ).toBeTruthy();
  });

  it("shows every quarter against the index and marks the ones it lost", async () => {
    getFundPerformance.mockResolvedValue(PERF);
    renderPanel();

    const table = await screen.findByRole("table", { name: /quarter by quarter/i });
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    expect(headers).toEqual(["", "2026 Q1", "2026 Q2 *"]);
    const rows = within(table).getAllByRole("row");
    expect(rows[1].textContent).toContain("+10.0%");
    expect(rows[2].textContent).toContain("+5.0%");
    const diff = within(rows[3]).getAllByRole("cell");
    expect(diff[0].textContent).toBe("+5.0 pp");
    expect(diff[1].textContent).toBe("-3.0 pp");
    expect(diff[1].getAttribute("aria-label")).toBe("2026 Q2: trailed the S&P 500 by 3.0 pp");
  });

  it("renders nothing for a fund without a measured quarter", async () => {
    getFundPerformance.mockResolvedValue(null);
    const { container } = renderPanel("Gamma");
    await vi.waitFor(() => expect(getFundPerformance).toHaveBeenCalledWith("Gamma"));
    expect(container.textContent).toBe("");
  });
});
