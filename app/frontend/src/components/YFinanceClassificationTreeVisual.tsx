import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Loader2, Search } from "lucide-react";

import { getSectorHierarchy } from "@/lib/dataService";
import { Input } from "@/components/ui/input";
import { PanelTitle } from "@/components/ui/PanelTitle";
import { getSectorStyle } from "@/lib/sectorStyle";
import { getIndustryIcon } from "@/lib/industryIcon";

interface Props {
  onSelectIndustry?: (industry: string) => void;
}

export default function YFinanceClassificationTreeVisual({ onSelectIndustry }: Props = {}) {
  const { data: hierarchy = [], isLoading } = useQuery({
    queryKey: ["sectorHierarchy"],
    queryFn: getSectorHierarchy,
  });

  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const [query, setQuery] = useState("");

  // Group industries by sector, lowercased query for case-insensitive search.
  const grouped = useMemo(() => {
    const map = new Map<string, string[]>();
    const q = query.trim().toLowerCase();
    for (const { sector, industry } of hierarchy) {
      if (q && !sector.toLowerCase().includes(q) && !industry.toLowerCase().includes(q)) continue;
      const list = map.get(sector) ?? [];
      list.push(industry);
      map.set(sector, list);
    }
    return [...map.entries()]
      .map(([sector, industries]) => ({ sector, industries: industries.sort() }))
      .sort((a, b) => a.sector.localeCompare(b.sector));
  }, [hierarchy, query]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading taxonomy…
      </div>
    );
  }

  const toggle = (sector: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(sector)) next.delete(sector);
      else next.add(sector);
      return next;
    });
  };

  // Auto-expand sectors when a query narrows results, so matches are visible
  // without manual clicks.
  const isExpanded = (sector: string) => expanded.has(sector) || query.trim().length > 0;

  return (
    <div className="frame">
      <div className="frame-title">
        <PanelTitle>Yahoo Finance Classification</PanelTitle>
        <div className="relative w-56">
          <Search
            className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search sector or industry…"
            aria-label="Search sector or industry"
            className="pl-8 h-7 text-xs font-normal"
          />
        </div>
      </div>

      <ul className="p-3 space-y-1">
        {grouped.length === 0 && <li className="text-xs text-muted-foreground">No matches.</li>}
        {grouped.map(({ sector, industries }) => {
          const Icon = getSectorStyle(sector).icon;
          const open = isExpanded(sector);
          return (
            <li key={sector}>
              <button
                type="button"
                onClick={() => toggle(sector)}
                aria-expanded={open}
                className="w-full flex items-center gap-2 px-2 h-8 text-left rounded-md hover:bg-muted transition-colors"
              >
                {open ? (
                  <ChevronDown
                    className="h-4 w-4 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />
                ) : (
                  <ChevronRight
                    className="h-4 w-4 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />
                )}
                <Icon className="h-4 w-4 text-muted-foreground shrink-0" aria-hidden="true" />
                <span className="text-[13px] font-medium text-foreground truncate">{sector}</span>
                <span className="ml-auto text-xs text-muted-foreground tabular-nums">
                  {industries.length}
                </span>
              </button>
              {open && (
                <ul className="ml-4 pl-3 py-1.5 border-l border-border grid grid-cols-1 gap-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {industries.map((industry) => {
                    const IndustryIcon = getIndustryIcon(industry) ?? Icon;
                    const inner = (
                      <>
                        <IndustryIcon
                          className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                          aria-hidden="true"
                        />
                        <span className="truncate">{industry}</span>
                      </>
                    );
                    return (
                      <li key={industry} className="min-w-0">
                        {onSelectIndustry ? (
                          <button
                            type="button"
                            onClick={() => onSelectIndustry(industry)}
                            title={industry}
                            className="w-full flex items-center gap-2 rounded-md px-2 h-8 text-left text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                          >
                            {inner}
                          </button>
                        ) : (
                          <div
                            title={industry}
                            className="flex items-center gap-2 px-2 h-8 text-xs text-muted-foreground"
                          >
                            {inner}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
