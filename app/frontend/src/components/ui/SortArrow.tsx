import { ArrowDown, ArrowUp } from "lucide-react";

import type { SortDir } from "@/hooks/useSortState";

/** Direction arrow next to the active column's label; renders nothing for inactive columns. */
export function SortArrow({ active, direction }: { active: boolean; direction: SortDir }) {
  if (!active) return null;
  const Icon = direction === "desc" ? ArrowDown : ArrowUp;
  return <Icon className="ml-1 inline-block h-3 w-3 align-[-1px]" aria-hidden="true" />;
}
