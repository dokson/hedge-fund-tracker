import { beforeEach, describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";

import { useStarred } from "./useStarred";

describe("useStarred localStorage hydration", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("reads back a valid stored list", () => {
    localStorage.setItem("starred_stock", JSON.stringify(["AAA", "BBB"]));
    const { result } = renderHook(() => useStarred("stock"));
    expect([...result.current.starred].sort()).toEqual(["AAA", "BBB"]);
  });

  it("drops non-string entries from corrupted storage", () => {
    localStorage.setItem("starred_stock", JSON.stringify(["AAA", 5, null, "BBB"]));
    const { result } = renderHook(() => useStarred("stock"));
    expect([...result.current.starred].sort()).toEqual(["AAA", "BBB"]);
  });

  it("falls back to an empty set when storage holds a non-array", () => {
    localStorage.setItem("starred_stock", JSON.stringify({ nope: true }));
    const { result } = renderHook(() => useStarred("stock"));
    expect(result.current.starred.size).toBe(0);
  });
});
