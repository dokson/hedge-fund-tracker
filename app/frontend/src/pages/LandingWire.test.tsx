import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import type * as DataService from "@/lib/dataService";
import type { EnrichedNQFiling, HedgeFund } from "@/lib/dataService";

const fund: HedgeFund = {
  cik: "1",
  fund: "Helikon",
  manager: "M",
  denomination: "Helikon LP",
  ciks: "",
  url: "https://helikon.example.com/",
};

const filing = (overrides: Partial<EnrichedNQFiling> = {}): EnrichedNQFiling => ({
  fund: "Helikon",
  cusip: "000000000",
  ticker: "PPLI",
  company: "Example Co",
  shares: 100,
  value: "$1M",
  avgPrice: "$10",
  date: "2026-10-05",
  filingDate: "2026-10-06",
  quarterShares: null,
  deltaShares: null,
  deltaType: "INCREASE",
  deltaPct: null,
  quarterPortfolioPct: null,
  estimatedPortfolioPct: null,
  ...overrides,
});

vi.mock("@/lib/dataService", async (importOriginal) => ({
  ...(await importOriginal<typeof DataService>()),
  getStocks: vi.fn<() => Promise<never[]>>(async () => []),
  getHedgeFunds: vi.fn<() => Promise<HedgeFund[]>>(async () => [fund]),
}));

vi.mock("@/hooks/useEnrichedNQFilings", () => ({
  useEnrichedNQFilings: () => ({
    data: [filing({}), filing({ fund: "Unlisted Fund", ticker: "CIGI" })],
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

vi.mock("@/hooks/useAvailableQuarters", () => ({
  useAvailableQuarters: () => ({ quarters: [], latestQuarter: undefined, isLoading: false }),
}));

import Landing from "./Landing";

describe("Landing latest-filings wire logos", () => {
  it("shows the fund's logo and the moved stock's logo on every row", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Landing />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const row = (await screen.findByRole("link", { name: "PPLI" })).closest("li")!;
    await waitFor(() => {
      expect(row.querySelector('img[src*="helikon.example.com"]')).not.toBeNull();
    });
    expect(row.querySelector('img[src*="PPLI"]')).not.toBeNull();

    // A fund missing from hedge_funds.csv still gets its initials avatar beside the name.
    const other = screen.getByRole("link", { name: "CIGI" }).closest("li")!;
    expect(other.textContent).toContain("UF");
  });
});
