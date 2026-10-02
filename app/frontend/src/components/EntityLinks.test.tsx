/**
 * Tests for the shared entity-link components. CompanyLink + TickerLink ship
 * the visual pill used across all tables, so the props contract (showLogo,
 * showStar, navigation target) is worth pinning.
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render } from "@testing-library/react";
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
          <Route path="/stock/:ticker" element={<div data-testid="stock-page" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CompanyLink", () => {
  it("navigates to /stock/<ticker> on click", () => {
    const { getByText, queryByTestId } = renderWithRouter(
      <CompanyLink ticker="AAPL" company="Apple Inc" />,
    );
    expect(queryByTestId("stock-page")).toBeNull();
    fireEvent.click(getByText("Apple Inc"));
    expect(queryByTestId("stock-page")).not.toBeNull();
  });

  it("renders a star button only when showStar is true", () => {
    const { container: withStar } = renderWithRouter(
      <CompanyLink ticker="AAPL" company="Apple Inc" showStar />,
    );
    expect(withStar.querySelectorAll("button").length).toBe(1);

    const { container: withoutStar } = renderWithRouter(
      <CompanyLink ticker="AAPL" company="Apple Inc" />,
    );
    expect(withoutStar.querySelectorAll("button").length).toBe(0);
  });
});

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

describe("TickerLink", () => {
  it("carries an optional title, so a stretched link can surface the company on hover", () => {
    const { getByRole } = renderWithRouter(
      <TickerLink ticker="NVDA" showLogo={false} title="Nvidia Corp" />,
    );
    expect(getByRole("link", { name: "NVDA" }).getAttribute("title")).toBe("Nvidia Corp");
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
