/**
 * Tests for the shared string helpers. `matchesQuery` backs every in-page
 * search box (filings, stocks, funds, config), so its "empty query matches
 * all / case-insensitive / null-safe" contract is relied on app-wide.
 */
import { describe, expect, it } from "vitest";

import { matchesQuery, toInitCap } from "./utils";

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

  it("returns false when no field contains the query", () => {
    expect(matchesQuery("zzz", "abc", "def")).toBe(false);
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
