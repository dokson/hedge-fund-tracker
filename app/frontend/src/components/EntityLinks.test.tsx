/**
 * Tests for shared entity navigation and decorative-logo fallback behavior.
 * Navigation targets and independent star controls must survive visual changes.
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { CompanyLink, FundCell, TickerLink } from "./EntityLinks";
import * as imageInk from "@/lib/imageInk";
// IntersectionObserver polyfill comes from src/test/setup.ts.

function renderWithRouter(ui: React.ReactElement, initialPath = "/") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(
    ["hedgeFunds"],
    [
      {
        fund: "Example_Fund",
        denomination: "Example Fund Management",
        manager: "Example Manager",
        url: "https://example.com",
      },
    ],
  );
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

  it("keeps the stock logo inside its navigation target without repeating its name", () => {
    const { getByRole, container } = renderWithRouter(<TickerLink ticker="AMZN" />);
    const link = getByRole("link", { name: "AMZN" });
    const img = container.querySelector("img")!;

    expect(link.getAttribute("href")).toBe("/stock/AMZN");
    expect(link.contains(img)).toBe(true);
    expect(img.alt).toBe("");
  });

  it("keeps the stock star independent of the company link", () => {
    const { getByRole } = renderWithRouter(
      <CompanyLink ticker="AAPL" company="Apple Inc" showStar />,
    );

    expect(getByRole("link").contains(getByRole("button"))).toBe(false);
  });

  it("includes the fund logo and manager within one real fund anchor", () => {
    const { getByRole, container } = renderWithRouter(<FundCell fundName="Example_Fund" />);
    const link = getByRole("link");
    const img = container.querySelector("img")!;

    expect(link.getAttribute("href")).toBe("/funds/Example_Fund");
    expect(link.contains(img)).toBe(true);
    expect(img.alt).toBe("");
    expect(link.querySelectorAll("a")).toHaveLength(0);
  });

  it("keeps fund navigation intact through the curated, generic and monogram fallbacks", () => {
    const { getByRole, container } = renderWithRouter(<FundCell fundName="Example_Fund" />);
    const curated = container.querySelector("img")!;
    expect(curated.src).toContain("/image/upload/funds/favicons/example.com.png");

    fireEvent.error(curated);
    const generic = container.querySelector("img")!;
    expect(generic.src).toBe("https://icon.horse/icon/example.com");

    fireEvent.error(generic);
    expect(container.querySelector("img")).toBeNull();
    expect(getByRole("link").getAttribute("href")).toBe("/funds/Example_Fund");
    expect(getByRole("link").querySelector("[aria-hidden='true']")).not.toBeNull();
  });

  it("skips blank fund assets before reaching the monogram fallback", () => {
    const blankImage = vi.spyOn(imageInk, "isBlankImage").mockReturnValue(true);
    try {
      const { container, getByRole } = renderWithRouter(<FundCell fundName="Example_Fund" />);
      fireEvent.load(container.querySelector("img")!);
      expect(container.querySelector("img")!.src).toBe("https://icon.horse/icon/example.com");

      fireEvent.load(container.querySelector("img")!);
      expect(container.querySelector("img")).toBeNull();
      expect(getByRole("link").getAttribute("href")).toBe("/funds/Example_Fund");
    } finally {
      blankImage.mockRestore();
    }
  });
});
