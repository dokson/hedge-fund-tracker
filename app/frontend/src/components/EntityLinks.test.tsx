/**
 * Tests for the shared entity-link components. CompanyLink + TickerLink ship
 * the visual pill used across all tables, so the props contract (showLogo,
 * showStar, navigation target) is worth pinning.
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
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
          <Route path="/stock/:ticker" element={<div data-testid="stock-page" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CompanyLink", () => {
  it("renders the company name", () => {
    const { getByText } = renderWithRouter(<CompanyLink ticker="AAPL" company="Apple Inc" />);
    expect(getByText("Apple Inc")).toBeDefined();
  });

  it("navigates to /stock/<ticker> on click", () => {
    const { getByText, queryByTestId } = renderWithRouter(
      <CompanyLink ticker="AAPL" company="Apple Inc" />,
    );
    expect(queryByTestId("stock-page")).toBeNull();
    fireEvent.click(getByText("Apple Inc"));
    expect(queryByTestId("stock-page")).not.toBeNull();
  });

  it("prepends a star button when showStar is true", () => {
    const { container, getByText } = renderWithRouter(
      <CompanyLink ticker="AAPL" company="Apple Inc" showStar />,
    );
    expect(getByText("Apple Inc")).toBeDefined();
    // Star is rendered as the first interactive node inside the wrapper.
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  it("omits the star button by default", () => {
    const { container } = renderWithRouter(<CompanyLink ticker="AAPL" company="Apple Inc" />);
    expect(container.querySelectorAll("button").length).toBe(0);
  });
});

describe("TickerLink", () => {
  it("renders the ticker text inside a .ticker-pill", () => {
    const { container, getByText } = renderWithRouter(<TickerLink ticker="NVDA" />);
    expect(getByText("NVDA")).toBeDefined();
    expect(container.querySelector(".ticker-pill")).not.toBeNull();
  });

  it("includes a logo by default and skips it when showLogo is false", () => {
    const { container: withLogo } = renderWithRouter(<TickerLink ticker="NVDA" />);
    expect(withLogo.querySelector("img")).not.toBeNull();

    const { container: withoutLogo } = renderWithRouter(
      <TickerLink ticker="NVDA" showLogo={false} />,
    );
    expect(withoutLogo.querySelector("img")).toBeNull();
  });
});
