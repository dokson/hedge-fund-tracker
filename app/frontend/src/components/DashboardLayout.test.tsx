import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DashboardLayout from "./DashboardLayout";

vi.mock("@/lib/dataService", () => ({
  getStocks: () => Promise.resolve([]),
  getHedgeFunds: () => Promise.resolve([]),
  getAvailableQuarters: () => Promise.resolve([]),
  getLatestQuarter: () => Promise.resolve("2026Q2"),
}));

describe("DashboardLayout top bar", () => {
  beforeEach(() => {
    // jsdom ships no matchMedia, which the sidebar's `useIsMobile` subscribes to.
    window.innerWidth = 390;
    window.matchMedia = (query: string): MediaQueryList => ({
      matches: true,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    });
  });

  it("always offers a way back to the home page, also on phones where the logo opens the menu", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/stocks"]}>
          <DashboardLayout>
            <p>page</p>
          </DashboardLayout>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const home = within(screen.getByLabelText("Top bar")).getByRole("link", { name: "Home" });
    expect(home.getAttribute("href")).toBe("/");
  });
});
