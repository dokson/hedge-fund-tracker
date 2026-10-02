import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Stock } from "@/lib/dataService";

vi.mock("@/lib/dataService", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/dataService")>()),
  getStocks: vi.fn<() => Promise<Stock[]>>(async () => [
    { cusip: "000000001", ticker: "AAA", company: "Alpha Co", sector: "Technology" },
  ]),
}));

vi.mock("@/hooks/useAvailableQuarters", () => ({
  useAvailableQuarters: () => ({ quarters: [], latestQuarter: "2026Q2", isLoading: false }),
}));

vi.mock("@/hooks/useQuarterAnalysis", () => ({
  useQuarterAnalysis: () => ({
    data: undefined,
    isLoading: false,
    isError: true,
    error: new Error("Failed to fetch analysis: 503"),
  }),
}));

import SectorHeatmap from "./SectorHeatmap";

describe("SectorHeatmap", () => {
  it("shows the quarter-analysis error instead of an empty heatmap", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SectorHeatmap />
      </QueryClientProvider>,
    );
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Failed to fetch analysis: 503");
  });
});
