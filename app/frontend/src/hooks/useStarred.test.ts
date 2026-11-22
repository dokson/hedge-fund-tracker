import { beforeEach, describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";

import { useStarred } from "./useStarred";

describe("useStarred localStorage hydration", () => {
  beforeEach(() => {
    localStorage.clear();
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

describe("useStarred on one page", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("shows a star set in one component to every other one at once", () => {
    // A table's star and the page's starred-stock scope are separate hook calls.
    const table = renderHook(() => useStarred("stock"));
    const scope = renderHook(() => useStarred("stock"));
    act(() => table.result.current.toggle("NVDA"));
    expect(scope.result.current.isStarred("NVDA")).toBe(true);
    expect([...scope.result.current.starred]).toEqual(["NVDA"]);
    act(() => scope.result.current.toggle("NVDA"));
    expect(table.result.current.isStarred("NVDA")).toBe(false);
  });

  it("keeps stocks and funds apart", () => {
    const stocks = renderHook(() => useStarred("stock"));
    const funds = renderHook(() => useStarred("fund"));
    act(() => stocks.result.current.toggle("Duquesne"));
    expect(funds.result.current.isStarred("Duquesne")).toBe(false);
  });
});
