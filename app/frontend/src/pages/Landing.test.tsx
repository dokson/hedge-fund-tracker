import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import type { EnrichedNQFiling } from "@/lib/dataService";

vi.mock("@/lib/dataService", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/dataService")>()),
  getStocks: vi.fn<() => Promise<never[]>>(async () => []),
  getHedgeFunds: vi.fn<() => Promise<never[]>>(async () => []),
  getEnrichedNQFilings: vi.fn<() => Promise<EnrichedNQFiling[]>>(async () => {
    throw new Error("Failed to fetch non_quarterly.csv: 503");
  }),
}));

vi.mock("@/hooks/useAvailableQuarters", () => ({
  useAvailableQuarters: () => ({ quarters: [], latestQuarter: undefined, isLoading: false }),
}));

import Landing from "./Landing";

describe("Landing latest-filings wire", () => {
  it("reports a failed load instead of claiming there are no filings", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Landing />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Failed to fetch non_quarterly.csv: 503");
    expect(screen.queryByText("No filings yet.")).toBeNull();
  });
});

describe("Landing feature claims", () => {
  // The code is proprietary (All Rights Reserved): source-available, not open source.
  it("never calls the project open source or self-hostable", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Landing />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const text = (container.textContent ?? "").toLowerCase();
    expect(text).not.toContain("open source");
    expect(text).not.toContain("self-hostable");
    expect(screen.getByText("Source available, runs in your browser")).toBeTruthy();
  });
});
