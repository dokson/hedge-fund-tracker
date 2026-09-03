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
  // The logo is decorative by default: it always sits beside the ticker or the
  // company name, so `alt={ticker}` announced the ticker twice (axe
  // `image-redundant-alt`, SC 1.1.1). `decorative={false}` restores the name
  // for a logo that stands alone.
  it("renders a decorative img by default", () => {
    const { container } = render(<CompanyLogo ticker="AAPL" size={48} />);
    const img = container.querySelector("img")!;

    expect(img.alt).toBe("");
    expect(img.width).toBe(48);
    expect(img.src).toContain("financialmodelingprep.com/symbol/AAPL.png");
  });

  it("names the img when it is not decorative", () => {
    const { getByRole } = render(<CompanyLogo ticker="AAPL" decorative={false} />);

    expect((getByRole("img") as HTMLImageElement).alt).toBe("AAPL");
  });

  it("falls back to a colored initial-letter avatar when the image fails to load", () => {
    const { container, getAllByRole } = render(<CompanyLogo ticker="UNKNOWN" decorative={false} />);
    const img = container.querySelector("img")!;

    fireEvent.error(img);

    const avatar = getAllByRole("img").find((el) => el.tagName !== "IMG");
    expect(avatar).toBeDefined();
    expect(avatar?.getAttribute("aria-label")).toBe("UNKNOWN logo");
    expect(avatar?.textContent).toBe("UNKN");
  });

  it("hides the fallback avatar from AT when decorative", () => {
    const { container } = render(<CompanyLogo ticker="UNKNOWN" />);
    fireEvent.error(container.querySelector("img")!);

    expect(container.querySelector("[aria-hidden='true']")?.textContent).toBe("UNKN");
  });

  it("renders a placeholder immediately when no ticker is provided", () => {
    const { queryByRole, container } = render(<CompanyLogo ticker="" />);

    expect(queryByRole("img")).toBeNull();
    expect(container.querySelector("[aria-label='Logo placeholder']")).not.toBeNull();
  });
});
