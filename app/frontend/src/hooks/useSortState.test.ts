import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useSortState } from "./useSortState";

type Key = "a" | "b";

describe("useSortState", () => {
  it("starts from the given key and direction", () => {
    const { result } = renderHook(() => useSortState<Key>("a", "asc"));
    expect(result.current.sortKey).toBe("a");
    expect(result.current.sortDir).toBe("asc");
  });

  it("defaults to descending", () => {
    const { result } = renderHook(() => useSortState<Key>("a"));
    expect(result.current.sortDir).toBe("desc");
  });

  it("flips the direction when the active key is toggled again", () => {
    const { result } = renderHook(() => useSortState<Key>("a"));
    act(() => result.current.toggleSort("a"));
    expect(result.current.sortDir).toBe("asc");
    act(() => result.current.toggleSort("a"));
    expect(result.current.sortDir).toBe("desc");
  });

  it("switches to a new key in descending order", () => {
    const { result } = renderHook(() => useSortState<Key>("a", "asc"));
    act(() => result.current.toggleSort("b"));
    expect(result.current.sortKey).toBe("b");
    expect(result.current.sortDir).toBe("desc");
  });

  it("sets key and direction explicitly", () => {
    const { result } = renderHook(() => useSortState<Key>("a"));
    act(() => result.current.setSort("b", "asc"));
    expect(result.current.sortKey).toBe("b");
    expect(result.current.sortDir).toBe("asc");
  });

  it("reports aria-sort per column", () => {
    const { result } = renderHook(() => useSortState<Key>("a"));
    expect(result.current.ariaSort("a")).toBe("descending");
    expect(result.current.ariaSort("b")).toBe("none");
  });

  it("builds a ColumnHeader sort descriptor", () => {
    const { result } = renderHook(() => useSortState<Key>("a"));
    const sortB = result.current.columnSort("b");
    expect(sortB.active).toBe(false);
    act(() => sortB.onToggle());
    expect(result.current.sortKey).toBe("b");
  });

  it("keeps toggleSort stable across renders", () => {
    const { result, rerender } = renderHook(() => useSortState<Key>("a"));
    const first = result.current.toggleSort;
    rerender();
    expect(result.current.toggleSort).toBe(first);
  });
});
