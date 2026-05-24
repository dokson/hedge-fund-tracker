import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Loader2, Search } from "lucide-react";

import { getSectorHierarchy } from "@/lib/dataService";
import { Input } from "@/components/ui/input";
import { getSectorStyle } from "@/lib/sectorStyle";

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
    <div className="rounded-lg border border-border bg-card p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="section-title text-sm">Yahoo Finance Classification</h3>
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search sector or industry…"
            className="pl-8 h-8 text-xs"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        {grouped.length === 0 && <p className="text-xs text-muted-foreground">No matches.</p>}
        {grouped.map(({ sector, industries }) => {
          const style = getSectorStyle(sector);
          const Icon = style.icon;
          const open = isExpanded(sector);
          return (
            <div
              key={sector}
              className={`rounded-md border ${style.border} ${style.bg} overflow-hidden`}
            >
              <button
                type="button"
                onClick={() => toggle(sector)}
                className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-muted/30 transition-colors"
              >
                {open ? (
                  <ChevronDown className={`h-4 w-4 ${style.color}`} />
                ) : (
                  <ChevronRight className={`h-4 w-4 ${style.color}`} />
                )}
                <Icon className={`h-4 w-4 ${style.color}`} />
                <span className="font-medium text-sm text-foreground">{sector}</span>
                <span className="ml-auto text-xs text-muted-foreground">{industries.length}</span>
              </button>
              {open && (
                <ul className="px-3 pb-2 pl-10 text-xs space-y-1">
                  {industries.map((industry) => (
                    <li key={industry}>
                      {onSelectIndustry ? (
                        <button
                          type="button"
                          onClick={() => onSelectIndustry(industry)}
                          className="text-muted-foreground hover:text-primary hover:underline focus-visible:text-primary focus-visible:underline focus-visible:outline-none transition-colors text-left cursor-pointer"
                        >
                          {industry}
                        </button>
                      ) : (
                        <span className="text-muted-foreground">{industry}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
