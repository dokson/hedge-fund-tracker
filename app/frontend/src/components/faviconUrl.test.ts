/**
 * Tests for buildFaviconUrl — the helper used by FundLogo. In local/dev mode
 * (IS_GH_PAGES_MODE=false at test time) the helper goes direct to icon.horse;
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

  it("strips a leading www. before asking icon.horse for the favicon", () => {
    const url = buildFaviconUrl("https://www.example.com/", 16);
    expect(url).toContain("example.com");
    expect(url).not.toContain("www.example.com");
  });

  it("targets the icon.horse endpoint", () => {
    const url = buildFaviconUrl("https://example.com/", 16);
    expect(url).toContain("icon.horse/icon/example.com");
  });

  it("URI-encodes the host", () => {
    const url = buildFaviconUrl("https://xn--bcher-kva.example/", 16);
    expect(url).toContain("xn--bcher-kva.example");
  });
});
