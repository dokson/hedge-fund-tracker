/**
 * The GH Pages logo chain: Cloudinary first, then the original source, then the monogram.
 * A refused CDN variant (strict transformations, 401) must never cost a logo that exists.
 */
import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type * as Config from "@/lib/config";

vi.mock("@/lib/config", async (importOriginal) => ({
  ...(await importOriginal<typeof Config>()),
  IS_GH_PAGES_MODE: true,
  CLOUDINARY_CLOUD_NAME: "demo",
}));
vi.mock("@/data/curatedFavicons.json", () => ({ default: ["kopernikglobal.com"] }));
vi.mock("@/data/curatedLogos.json", () => ({ default: ["IRLA"] }));

import { CompanyLogo } from "./CompanyLogo";
import { FundLogo } from "./FundLogo";
import { buildLogoUrls } from "./companyLogoUrl";
import { buildFaviconUrls } from "./faviconUrl";

const FMP_NAK = "https://images.financialmodelingprep.com/symbol/NAK.png";

describe("logo sources on GH Pages", () => {
  it("lists the original source after the CDN, for stocks and funds", () => {
    const [cdn, direct] = buildLogoUrls("NAK", 40);
    expect(cdn).toContain("res.cloudinary.com/demo/image/fetch/");
    expect(direct).toBe(FMP_NAK);

    const fund = buildFaviconUrls("https://kopernikglobal.com", 28);
    expect(fund).toHaveLength(3);
    expect(fund[1]).toContain("res.cloudinary.com/demo/image/fetch/");
    expect(fund[2]).toBe("https://icon.horse/icon/kopernikglobal.com");
  });

  it("tries a stock's uploaded logo first, before the FMP sources it stands in for", () => {
    const [curated, cdn, direct] = buildLogoUrls("IRLA", 40);
    expect(curated).toBe("https://res.cloudinary.com/demo/image/upload/stocks/logos/IRLA.png");
    expect(cdn).toContain("res.cloudinary.com/demo/image/fetch/");
    expect(direct).toBe("https://images.financialmodelingprep.com/symbol/IRLA.png");
  });

  it("never asks Cloudinary for a curated favicon the manifest does not list", () => {
    const fund = buildFaviconUrls("https://www.uncurated.example", 28);
    expect(fund).toHaveLength(2);
    expect(fund.some((url) => url.includes("/image/upload/"))).toBe(false);
    expect(fund[1]).toBe("https://icon.horse/icon/uncurated.example");
  });

  it("falls back to the original logo when the CDN refuses, not to the monogram", () => {
    const { container } = render(<CompanyLogo ticker="NAK" size={40} eager />);
    fireEvent.error(container.querySelector("img")!);
    expect(container.querySelector("img")?.getAttribute("src")).toBe(FMP_NAK);
  });

  it("starts over for the next ticker instead of carrying the last one's failure", () => {
    const { container, rerender } = render(<CompanyLogo ticker="NAK" size={40} eager />);
    fireEvent.error(container.querySelector("img")!);
    fireEvent.error(container.querySelector("img")!);
    expect(container.querySelector("img")).toBeNull();
    rerender(<CompanyLogo ticker="NVDA" size={40} eager />);
    expect(container.querySelector("img")?.getAttribute("src")).toContain("res.cloudinary.com");
  });

  it("tries icon.horse directly when its CDN copy fails", () => {
    const { container } = render(
      <FundLogo fundName="Kopernik" url="https://kopernikglobal.com" size={28} eager />,
    );
    fireEvent.error(container.querySelector("img")!); // curated asset missing
    fireEvent.error(container.querySelector("img")!); // CDN refuses
    expect(container.querySelector("img")?.getAttribute("src")).toBe(
      "https://icon.horse/icon/kopernikglobal.com",
    );
  });
});
