import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { ResearchProvider } from "@/components/ResearchProvider";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { PerformanceData, PerfSeries } from "@/lib/dataService";

vi.mock("@/lib/dataService", () => ({
  getPerformance: vi.fn<() => Promise<PerformanceData>>(async () => performance),
}));

vi.mock("@/components/EquityCurveChart", () => ({
  default: ({
    series,
    band,
  }: {
    series: PerfSeries[];
    band?: { baseId: string; topId: string };
  }) => (
    <output aria-label="Plotted series">
      {JSON.stringify({ ids: series.map((item) => item.id), band })}
    </output>
  ),
}));

vi.mock("@/components/CompositionPanel", () => ({
  default: ({ strategyId }: { strategyId: string }) => (
    <div aria-label="Strategy holdings">{strategyId}</div>
  ),
}));

import StrategyPerformance from "./StrategyPerformance";

function series(id: string, label: string, type: PerfSeries["type"]): PerfSeries {
  return {
    id,
    label,
    type,
    windows: [{ quarterOut: "2025Q2", windowReturn: 0.1, cumReturn: 0.1, excessReturn: null }],
    cumReturn: 0.1,
    volatility: 0,
    excessPp: type === "benchmark" ? null : 2,
    beats: 1,
    total: 1,
  };
}

const performance: PerformanceData = {
  quarters: ["2025Q2"],
  startDate: "2025-05-15",
  startQuarter: "2025Q1",
  series: [
    series("smart_score", "Smart Score", "strategy"),
    series("avg_portfolio", "Average Portfolio", "strategy"),
    series("SPY", "S&P 500", "benchmark"),
  ],
};

function renderPerformance(path = "/performance") {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[path]}>
          <ResearchProvider>
            <StrategyPerformance />
          </ResearchProvider>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

function plottedSeries() {
  return JSON.parse(screen.getByLabelText("Plotted series").textContent ?? "{}");
}

describe("Performance series selection", () => {
  it("preserves deep-link isolation and lets the compact legend switch or clear the strategy", async () => {
    renderPerformance("/performance?strategy=smart_score");
    const legend = await screen.findByRole("group", { name: "Chart series" });
    expect(plottedSeries()).toMatchObject({
      ids: ["smart_score", "SPY"],
      band: { baseId: "SPY", topId: "smart_score" },
    });
    expect(screen.getByLabelText("Strategy holdings").textContent).toBe("smart_score");
    expect(
      within(legend).getByRole("button", { name: "Smart Score" }).getAttribute("aria-pressed"),
    ).toBe("true");
    expect(within(legend).queryByRole("button", { name: "S&P 500" })).toBeNull();
    expect(within(legend).getByText("S&P 500")).toBeTruthy();

    const average = within(legend).getByRole("button", { name: "Average Portfolio" });
    fireEvent.click(average);
    expect(plottedSeries().ids).toEqual(["avg_portfolio", "SPY"]);
    expect(screen.getByLabelText("Strategy holdings").textContent).toBe("avg_portfolio");
    fireEvent.click(average);
    expect(plottedSeries().ids).toEqual(["smart_score", "avg_portfolio", "SPY"]);
    expect(plottedSeries().band).toBeUndefined();
    expect(screen.queryByLabelText("Strategy holdings")).toBeNull();
  });

  it("keeps detail-table selection synchronized with the compact legend and Show all", async () => {
    renderPerformance();
    const table = await screen.findByRole("table", { name: "Strategy legend and series toggle" });
    fireEvent.click(within(table).getByRole("button", { name: "Smart Score" }));
    const legend = screen.getByRole("group", { name: "Chart series" });
    expect(
      within(legend).getByRole("button", { name: "Smart Score" }).getAttribute("aria-pressed"),
    ).toBe("true");
    expect(plottedSeries().ids).toEqual(["smart_score", "SPY"]);
    fireEvent.click(screen.getByRole("button", { name: "Show all" }));
    expect(
      within(legend).getByRole("button", { name: "Smart Score" }).getAttribute("aria-pressed"),
    ).toBe("false");
    expect(plottedSeries().ids).toEqual(["smart_score", "avg_portfolio", "SPY"]);
  });
});
