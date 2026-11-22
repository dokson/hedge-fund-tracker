/**
 * Tests for buildFaviconUrls — the sources FundLogo tries. In local/dev mode
 * (IS_GH_PAGES_MODE=false at test time) icon.horse is hit directly after the
 * curated asset; the GH Pages chain is covered in logoSources.gh.test.tsx.
 */
import { describe, expect, it } from "vitest";

import { buildFaviconUrls } from "./faviconUrl";

describe("buildFaviconUrls", () => {
  it("has nothing to try when no URL is provided", () => {
    expect(buildFaviconUrls(undefined, 16)).toEqual([]);
    expect(buildFaviconUrls(null, 16)).toEqual([]);
    expect(buildFaviconUrls("", 16)).toEqual([]);
  });

  it("has nothing to try for unparseable URLs", () => {
    expect(buildFaviconUrls("not a url", 16)).toEqual([]);
  });

  it("strips a leading www. before asking for the favicon", () => {
    const urls = buildFaviconUrls("https://www.example.com/", 16);
    expect(urls.length).toBeGreaterThan(0);
    for (const url of urls) {
      expect(url).toContain("example.com");
      expect(url).not.toContain("www.example.com");
    }
  });
});
