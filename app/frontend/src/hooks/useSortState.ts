import { useCallback, useState } from "react";

import type { ColumnSort } from "@/components/ui/ColumnHeader";

export type SortDir = "asc" | "desc";

/**
 * Sortable-table state shared by every data table: clicking the active column
 * flips the direction, clicking another column sorts it descending.
 */
export function useSortState<K extends string>(defaultKey: K, defaultDir: SortDir = "desc") {
  const [sort, setSortState] = useState<{ key: K; dir: SortDir }>({
    key: defaultKey,
    dir: defaultDir,
  });

  const toggleSort = useCallback((key: K) => {
    setSortState((prev) =>
      prev.key === key ? { key, dir: prev.dir === "desc" ? "asc" : "desc" } : { key, dir: "desc" },
    );
  }, []);

  const setSort = useCallback((key: K, dir: SortDir) => setSortState({ key, dir }), []);

  const ariaSort = (key: K): "ascending" | "descending" | "none" =>
    sort.key === key ? (sort.dir === "desc" ? "descending" : "ascending") : "none";

  const columnSort = (key: K): ColumnSort => ({
    active: sort.key === key,
    direction: sort.dir,
    onToggle: () => toggleSort(key),
  });

  return { sortKey: sort.key, sortDir: sort.dir, toggleSort, setSort, ariaSort, columnSort };
}
