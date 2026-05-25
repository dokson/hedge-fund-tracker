/**
 * Tests for buildFaviconUrl — the helper used by FundLogo. In local/dev mode
 * (IS_GH_PAGES_MODE=false at test time) the helper goes direct to Google S2;
 * in production GH Pages mode it would wrap through Cloudinary's fetch CDN.
 */
import { describe, expect, it } from "vitest";

import { buildFaviconUrl } from "./faviconUrl";

describe("buildFaviconUrl", () => {
  it("returns null when no URL is provided", () => {
    expect(buildFaviconUrl(undefined, 16)).toBeNull();
    expect(buildFaviconUrl(null, 16)).toBeNull();
    expect(buildFaviconUrl("", 16)).toBeNull();
  });

  it("returns null for unparseable URLs", () => {
    expect(buildFaviconUrl("not a url", 16)).toBeNull();
  });

  it("strips a leading www. before asking Google for the favicon", () => {
    const url = buildFaviconUrl("https://www.example.com/", 16);
    expect(url).toContain("domain=example.com");
    expect(url).not.toContain("www.example.com");
  });

  it("requests a source large enough for retina + dpr_auto headroom", () => {
    const url = buildFaviconUrl("https://example.com/", 16);
    expect(url).toContain("sz=64");
  });

  it("snaps non-bucket sizes up to the next valid Google s2 bucket", () => {
    const url = buildFaviconUrl("https://example.com/", 20);
    expect(url).toContain("sz=128");
  });

  it("URI-encodes the domain", () => {
    // Hostnames with unusual characters are unlikely but the helper must not
    // throw and must produce a URL safe for direct browser consumption.
    const url = buildFaviconUrl("https://xn--bcher-kva.example/", 16);
    expect(url).toContain("xn--bcher-kva.example");
  });
});
