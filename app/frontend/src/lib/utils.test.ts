/**
 * Tests for the shared string helpers. `matchesQuery` backs every in-page
 * search box (filings, stocks, funds, config), so its "empty query matches
 * all / case-insensitive / null-safe" contract is relied on app-wide.
 */
import { afterEach, describe, expect, it } from "vitest";

import { isoDaysBefore, matchesQuery, toInitCap } from "./utils";

describe("matchesQuery", () => {
  it("matches everything when the query is empty or whitespace", () => {
    expect(matchesQuery("", "anything")).toBe(true);
    expect(matchesQuery("   ", "anything")).toBe(true);
  });

  it("is a case-insensitive substring match across all fields", () => {
    expect(matchesQuery("cap", "Foo", "Bar Capital")).toBe(true);
    expect(matchesQuery("FOO", "foo bar")).toBe(true);
    expect(matchesQuery("bar", "Foo")).toBe(false);
  });

  it("skips null / undefined fields without throwing", () => {
    expect(matchesQuery("axe", null, undefined, "an axe")).toBe(true);
    expect(matchesQuery("zzz", null, undefined)).toBe(false);
  });
});

describe("toInitCap", () => {
  it("title-cases each word", () => {
    expect(toInitCap("foo bar")).toBe("Foo Bar");
  });

  it("capitalises after hyphens and slashes", () => {
    expect(toInitCap("foo-bar/baz")).toBe("Foo-Bar/Baz");
  });

  it("returns an empty string for nullish input", () => {
    expect(toInitCap("")).toBe("");
    expect(toInitCap(null)).toBe("");
    expect(toInitCap(undefined)).toBe("");
  });
});

describe("isoDaysBefore", () => {
  it("returns the ISO date the given number of days before", () => {
    expect(isoDaysBefore(new Date(2026, 9, 2, 12), 30)).toBe("2026-09-02");
  });

  it("crosses month and year boundaries", () => {
    expect(isoDaysBefore(new Date(2026, 0, 5, 12), 10)).toBe("2025-12-26");
  });

  it("does not mutate the reference date", () => {
    const ref = new Date(2026, 9, 2, 12);
    isoDaysBefore(ref, 30);
    expect(ref.getDate()).toBe(2);
  });

  describe("in a timezone far from UTC", () => {
    const originalTz = process.env.TZ;
    afterEach(() => {
      if (originalTz === undefined) delete process.env.TZ;
      else process.env.TZ = originalTz;
    });

    it("formats the local date even when the UTC date differs (UTC+14, local 00:30)", () => {
      process.env.TZ = "Pacific/Kiritimati";
      expect(isoDaysBefore(new Date(2026, 9, 2, 0, 30), 1)).toBe("2026-10-01");
    });

    it("formats the local date even when the UTC date differs (UTC-10, local 23:30)", () => {
      process.env.TZ = "Pacific/Honolulu";
      expect(isoDaysBefore(new Date(2026, 9, 2, 23, 30), 1)).toBe("2026-10-01");
    });
  });
});
