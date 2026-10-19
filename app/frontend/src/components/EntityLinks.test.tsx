/**
 * Tests for the shared entity-link components. CompanyLink + TickerLink ship
 * the visual pill used across all tables, so the props contract (showLogo,
 * showStar, navigation target) is worth pinning.
 */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { CompanyLink, TickerLink } from "./EntityLinks";
// IntersectionObserver polyfill comes from src/test/setup.ts.

function renderWithRouter(ui: React.ReactElement, initialPath = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// These used to be `role="link"` spans driven by navigate(). They are real
// anchors now, so middle-click / cmd-click / "copy link address" work; these
// two cases pin the href so that cannot silently regress.
describe("entity links are real anchors", () => {
  it("gives CompanyLink an href to the stock page", () => {
    const { getByRole } = renderWithRouter(<CompanyLink ticker="AAPL" company="Apple Inc" />);
    expect(getByRole("link", { name: "Apple Inc" }).getAttribute("href")).toBe("/stock/AAPL");
  });

  it("gives TickerLink an href to the stock page", () => {
    const { getByRole } = renderWithRouter(<TickerLink ticker="NVDA" showLogo={false} />);
    expect(getByRole("link", { name: "NVDA" }).getAttribute("href")).toBe("/stock/NVDA");
  });
});
