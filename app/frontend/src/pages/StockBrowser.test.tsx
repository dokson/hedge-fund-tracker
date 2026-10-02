import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { Stock } from "@/lib/dataService";

vi.mock("@/lib/dataService", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/dataService")>()),
  getStocks: vi.fn<() => Promise<Stock[]>>(async () => [
    { cusip: "000000001", ticker: "AAA", company: "Alpha Co" },
  ]),
}));

vi.mock("@/hooks/useAvailableQuarters", () => ({
  useAvailableQuarters: () => ({ quarters: [], latestQuarter: undefined, isLoading: false }),
}));

import StockBrowser from "./StockBrowser";
import { stockPath, stocksByIndustry } from "@/lib/routes";

function LocationProbe() {
  return <output data-testid="location-search">{useLocation().search}</output>;
}

function renderAt(path: string) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[path]}>
          <StockBrowser />
          <LocationProbe />
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

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
