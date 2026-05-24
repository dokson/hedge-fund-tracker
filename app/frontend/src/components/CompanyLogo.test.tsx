/**
 * Tests for CompanyLogo — the URL builder produces the Cloudinary fetch URL
 * around FMP's public logo endpoint, and the component degrades gracefully to
 * a placeholder when the source 404s.
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render } from "@testing-library/react";

import { CompanyLogo } from "./CompanyLogo";
import { buildLogoUrl } from "./companyLogoUrl";

// IntersectionObserver polyfill comes from src/test/setup.ts.

describe("buildLogoUrl", () => {
  it("returns the FMP source URL directly in local mode (Cloudinary only on GH Pages)", () => {
    const url = buildLogoUrl("AAPL", 32);

    expect(url).toBe("https://images.financialmodelingprep.com/symbol/AAPL.png");
  });

  it("uri-encodes tickers containing slashes or special characters", () => {
    const url = buildLogoUrl("BRK/B", 32);

    expect(url).not.toContain("BRK/B.png");
    expect(url).toContain("BRK%2FB.png");
  });
});

describe("CompanyLogo", () => {
  it("renders an img with the ticker as alt text", () => {
    const { getByRole } = render(<CompanyLogo ticker="AAPL" size={48} />);
    const img = getByRole("img") as HTMLImageElement;

    expect(img.alt).toBe("AAPL");
    expect(img.width).toBe(48);
    expect(img.src).toContain("financialmodelingprep.com/symbol/AAPL.png");
  });

  it("falls back to a colored initial-letter avatar when the image fails to load", () => {
    const { getAllByRole } = render(<CompanyLogo ticker="UNKNOWN" />);
    const img = getAllByRole("img")[0];

    fireEvent.error(img);

    const avatar = getAllByRole("img").find((el) => el.tagName !== "IMG");
    expect(avatar).toBeDefined();
    expect(avatar?.getAttribute("aria-label")).toBe("UNKNOWN logo");
    expect(avatar?.textContent).toBe("UNKN");
  });

  it("renders a placeholder immediately when no ticker is provided", () => {
    const { queryByRole, container } = render(<CompanyLogo ticker="" />);

    expect(queryByRole("img")).toBeNull();
    expect(container.querySelector("[aria-label='Logo placeholder']")).not.toBeNull();
  });
});
