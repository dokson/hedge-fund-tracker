import { useState, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getEnrichedNQFilings,
  getStocks,
  parseValueString,
  clearCache,
  type EnrichedNQFiling,
} from "@/lib/dataService";
import { getSectorStyle } from "@/lib/sectorStyle";
import { TickerLink, FundCell, CompanyLink } from "@/components/EntityLinks";
import { Delta } from "@/components/Delta";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Loader2,
  ArrowUpRight,
  ArrowDownRight,
  Plus,
  X,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  FileText,
  Check,
  Star,
  Users,
  Building2,
} from "lucide-react";
import { toInitCap } from "@/lib/utils";
import { useStarred } from "@/hooks/useStarred";

/**
 * Inline sector pill for the Latest Filings table. Lives as a top-level
 * component (not an IIFE inside the row) so React Compiler can optimise it.
 */
function SectorPill({ sector, industry }: { sector?: string; industry?: string }) {
  if (!sector) {
    return <span className="text-muted-foreground/50">—</span>;
  }
  const style = getSectorStyle(sector);
  const Icon = style.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${style.border} ${style.bg} ${style.color} px-2 py-0.5 font-medium`}
      title={industry ?? sector}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {sector}
    </span>
  );
}

function formatDelta(f: EnrichedNQFiling): { text: string; className: string; sortValue: number } {
  if (f.deltaType === "CLOSED")
    return { text: "CLOSE", className: "text-rose-700 dark:text-rose-400", sortValue: -Infinity };
  if (f.deltaType === "NEW")
    return { text: "NEW", className: "text-teal-700 dark:text-teal-400", sortValue: Infinity };
  if (f.deltaType === "NO CHANGE")
    return { text: "+0%", className: "text-muted-foreground", sortValue: 0 };
  if (f.deltaPct !== null) {
    const sign = f.deltaPct > 0 ? "+" : "";
    const cls = f.deltaPct > 0 ? "text-positive" : "text-negative";
    return { text: `${sign}${f.deltaPct.toFixed(1)}%`, className: cls, sortValue: f.deltaPct };
  }
  return { text: "NEW", className: "text-teal-700 dark:text-teal-400", sortValue: Infinity };
}

type SortField = "date" | "delta" | "value" | null;
type SortDir = "asc" | "desc";

function SortIcon({
  field,
  currentField,
  direction,
}: {
  field: SortField;
  currentField: SortField;
  direction: SortDir;
}) {
  if (currentField !== field) return <ArrowUpDown className="h-3 w-3 ml-1 opacity-40" />;
  return direction === "asc" ? (
    <ArrowUp className="h-3 w-3 ml-1 text-primary" />
  ) : (
    <ArrowDown className="h-3 w-3 ml-1 text-primary" />
  );
}

export default function Dashboard() {
  const [search, setSearch] = useState("");
  const [fundFilter, setFundFilter] = useState("all");
  const [typeFilters, setTypeFilters] = useState<Set<string>>(() => new Set());
  const [daysBackPick, setDaysBackPick] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>("date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const { starred: starredStocks } = useStarred("stock");
  const { starred: starredFunds } = useStarred("fund");
  const [filterStarredStocks, setFilterStarredStocks] = useState(false);
  const [filterStarredFunds, setFilterStarredFunds] = useState(false);
  const hasAnyStarred = starredStocks.size > 0 || starredFunds.size > 0;

  const { data: filings = [], isLoading } = useQuery({
    queryKey: ["enrichedNQFilings"],
    queryFn: () => {
      clearCache("enriched_nq");
      return getEnrichedNQFilings();
    },
  });

  const { data: stocks = [] } = useQuery({ queryKey: ["stocks"], queryFn: getStocks });
  const tickerMeta = useMemo(() => {
    const map = new Map<string, { industry?: string; sector?: string }>();
    for (const s of stocks) {
      if (!map.has(s.ticker)) {
        map.set(s.ticker, { industry: s.industry, sector: s.sector });
      }
    }
    return map;
  }, [stocks]);

  const fundNames = useMemo(() => {
    // Defensive filter — a malformed row in non_quarterly.csv could yield
    // undefined/"", and the rendered <SelectItem>.replace would crash.
    const names = [...new Set(filings.map((f) => f.fund).filter(Boolean))];
    return names.sort();
  }, [filings]);

  const toggleSort = useCallback(
    (field: SortField) => {
      if (sortField === field) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortField(field);
        setSortDir("desc");
      }
    },
    [sortField],
  );

  const autoDaysBack = useMemo(() => {
    if (filings.length === 0) return "30";
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 30);
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    return filings.some((f) => f.date >= cutoffStr) ? "30" : "9999";
  }, [filings]);
  const daysBack = daysBackPick ?? autoDaysBack;

  const filtered = useMemo(() => {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - parseInt(daysBack));
    const cutoffStr = cutoff.toISOString().slice(0, 10);

    let rows = filings.filter((f) => {
      if (f.date < cutoffStr) return false;
      if (fundFilter !== "all" && f.fund !== fundFilter) return false;
      if (typeFilters.size > 0 && !typeFilters.has(f.deltaType)) return false;
      if (filterStarredFunds && starredFunds.size > 0 && !starredFunds.has(f.fund)) return false;
      if (filterStarredStocks && starredStocks.size > 0 && !starredStocks.has(f.ticker))
        return false;
      if (search) {
        const q = search.toLowerCase();
        if (
          !f.ticker.toLowerCase().includes(q) &&
          !f.fund.toLowerCase().includes(q) &&
          !f.company.toLowerCase().includes(q)
        )
          return false;
      }
      return true;
    });

    if (sortField) {
      rows = [...rows].sort((a, b) => {
        let cmp = 0;
        if (sortField === "date") {
          cmp = a.date.localeCompare(b.date);
        } else if (sortField === "delta") {
          cmp = formatDelta(a).sortValue - formatDelta(b).sortValue;
        } else if (sortField === "value") {
          cmp = parseValueString(a.value) - parseValueString(b.value);
        }
        return sortDir === "asc" ? cmp : -cmp;
      });
    }

    return rows;
  }, [
    filings,
    fundFilter,
    typeFilters,
    search,
    sortField,
    sortDir,
    daysBack,
    filterStarredFunds,
    filterStarredStocks,
    starredFunds,
    starredStocks,
  ]);

  const counts = useMemo(() => {
    const c = { NEW: 0, INCREASE: 0, DECREASE: 0, CLOSED: 0 };
    for (const f of filings) {
      if (f.deltaType in c) c[f.deltaType as keyof typeof c]++;
    }
    return c;
  }, [filings]);

  return (
    <div className="space-y-5 max-w-screen-2xl">
      <div>
        <h1 className="page-title">
          <FileText className="page-title-icon" /> Latest Filings
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Last 30 days 13D/G and Form 4 — latest filing per position, delta vs last 13F quarter
        </p>
      </div>

      {!isLoading && filings.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {(["NEW", "INCREASE", "DECREASE", "CLOSED"] as const).map((type) => {
            const isActive = typeFilters.has(type);
            const colorClasses = {
              NEW: {
                active:
                  "bg-[hsl(217,91%,60%)]/15 text-[hsl(217,91%,60%)] border-[hsl(217,91%,60%)] ring-2 ring-[hsl(217,91%,60%)]/30 ring-offset-1 ring-offset-background",
                inactive:
                  "bg-transparent text-muted-foreground border-border hover:border-[hsl(217,91%,60%)]/40 hover:text-[hsl(217,91%,60%)]",
              },
              INCREASE: {
                active:
                  "bg-positive/15 text-positive border-positive ring-2 ring-positive/30 ring-offset-1 ring-offset-background",
                inactive:
                  "bg-transparent text-muted-foreground border-border hover:border-positive/40 hover:text-positive",
              },
              DECREASE: {
                active:
                  "bg-negative/15 text-negative border-negative ring-2 ring-negative/30 ring-offset-1 ring-offset-background",
                inactive:
                  "bg-transparent text-muted-foreground border-border hover:border-negative/40 hover:text-negative",
              },
              CLOSED: {
                active:
                  "bg-[hsl(0,62%,45%)]/15 text-[hsl(0,62%,45%)] border-[hsl(0,62%,45%)] ring-2 ring-[hsl(0,62%,45%)]/30 ring-offset-1 ring-offset-background",
                inactive:
                  "bg-transparent text-muted-foreground border-border hover:border-[hsl(0,62%,45%)]/40 hover:text-[hsl(0,62%,45%)]",
              },
            }[type];
            const icon = { NEW: Plus, INCREASE: ArrowUpRight, DECREASE: ArrowDownRight, CLOSED: X }[
              type
            ];
            const Icon = icon;
            const label = {
              NEW: "New",
              INCREASE: "Increased",
              DECREASE: "Decreased",
              CLOSED: "Closed",
            }[type];
            const toggle = () =>
              setTypeFilters((prev) => {
                const next = new Set(prev);
                if (next.has(type)) next.delete(type);
                else next.add(type);
                return next;
              });
            return (
              <button
                key={type}
                onClick={toggle}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold border transition-all cursor-pointer select-none ${
                  isActive ? colorClasses.active : colorClasses.inactive
                }`}
              >
                <Icon className="h-3 w-3" />
                {counts[type]} {label}
                {isActive && <Check className="h-3 w-3 ml-0.5" />}
              </button>
            );
          })}
        </div>
      )}

      {hasAnyStarred && (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Star className="h-3 w-3" fill="currentColor" /> Consider Starred only:
          </span>
          <button
            onClick={() => starredFunds.size > 0 && setFilterStarredFunds((v) => !v)}
            disabled={starredFunds.size === 0}
            className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md border transition-colors ${
              filterStarredFunds
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-card border-border text-muted-foreground hover:text-foreground hover:border-foreground/30"
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            <Users className="h-3 w-3" /> Funds
            <Badge variant="secondary" className="text-[9px] px-1.5 py-0 h-4 leading-none">
              {starredFunds.size}
            </Badge>
          </button>
          <button
            onClick={() => starredStocks.size > 0 && setFilterStarredStocks((v) => !v)}
            disabled={starredStocks.size === 0}
            className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md border transition-colors ${
              filterStarredStocks
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-card border-border text-muted-foreground hover:text-foreground hover:border-foreground/30"
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            <Building2 className="h-3 w-3" /> Stocks
            <Badge variant="secondary" className="text-[9px] px-1.5 py-0 h-4 leading-none">
              {starredStocks.size}
            </Badge>
          </button>
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <Input
          placeholder="Search fund, ticker, company…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-64 bg-card border-border"
        />
        <Select value={fundFilter} onValueChange={setFundFilter}>
          <SelectTrigger className="w-48 bg-card border-border">
            <SelectValue placeholder="All Funds" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Funds</SelectItem>
            {fundNames.map((name) => (
              <SelectItem key={name} value={name}>
                {name.replace(/_/g, " ")}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={daysBack} onValueChange={setDaysBackPick}>
          <SelectTrigger className="w-36 bg-card border-border">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="30">Last 30 days</SelectItem>
            <SelectItem value="9999">All</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        {isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading and enriching filings…
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-muted-foreground uppercase tracking-wider">
                  <th className="text-left p-3 font-medium">Ticker</th>
                  <th className="text-left p-3 font-medium">Company</th>
                  <th className="text-left p-3 font-medium">Sector</th>
                  <th className="text-left p-3 font-medium">Fund</th>
                  <th
                    className="text-left p-3 font-medium cursor-pointer select-none hover:text-foreground transition-colors"
                    onClick={() => toggleSort("date")}
                  >
                    <span className="inline-flex items-center">
                      Date <SortIcon field="date" currentField={sortField} direction={sortDir} />
                    </span>
                  </th>
                  <th
                    className="text-right p-3 font-medium cursor-pointer select-none hover:text-foreground transition-colors"
                    onClick={() => toggleSort("delta")}
                  >
                    <span className="inline-flex items-center justify-end">
                      Delta <SortIcon field="delta" currentField={sortField} direction={sortDir} />
                    </span>
                  </th>
                  <th
                    className="text-right p-3 font-medium"
                    title="Position weight in the fund's last 13F portfolio"
                  >
                    Portfolio %
                  </th>
                  <th className="text-right p-3 font-medium">Avg Price</th>
                  <th
                    className="text-right p-3 font-medium cursor-pointer select-none hover:text-foreground transition-colors"
                    onClick={() => toggleSort("value")}
                  >
                    <span className="inline-flex items-center justify-end">
                      Value <SortIcon field="value" currentField={sortField} direction={sortDir} />
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="p-8 text-center text-muted-foreground">
                      No filings match your filters.
                    </td>
                  </tr>
                ) : (
                  filtered.map((f, i) => {
                    const borderClass =
                      f.deltaType === "CLOSED" || f.deltaType === "DECREASE"
                        ? "border-l-2 border-l-negative"
                        : f.deltaType === "NEW" || f.deltaType === "INCREASE"
                          ? "border-l-2 border-l-positive"
                          : "border-l-2 border-l-muted";

                    return (
                      <tr
                        key={`${f.cusip}-${f.fund}-${f.date}-${f.deltaType}-${f.shares ?? i}`}
                        className={`data-table-row ${borderClass}`}
                      >
                        <td className="p-3">
                          <TickerLink ticker={f.ticker} />
                        </td>
                        <td className="p-3">
                          <CompanyLink
                            ticker={f.ticker}
                            company={toInitCap(f.company)}
                            className="max-w-[180px] xl:max-w-[260px]"
                            showStar
                          />
                        </td>
                        <td className="p-3 text-xs whitespace-nowrap">
                          <SectorPill
                            sector={tickerMeta.get(f.ticker)?.sector}
                            industry={tickerMeta.get(f.ticker)?.industry}
                          />
                        </td>
                        <td className="p-3">
                          <FundCell fundName={f.fund} />
                        </td>
                        <td className="p-3 text-muted-foreground whitespace-nowrap">{f.date}</td>
                        <td className="p-3 text-right font-mono">
                          {f.deltaType === "NEW" ? (
                            <span className="badge-new">NEW</span>
                          ) : f.deltaType === "CLOSED" ? (
                            <span className="badge-closed">CLOSE</span>
                          ) : f.deltaPct !== null ? (
                            <Delta value={f.deltaPct} mode="percent" />
                          ) : (
                            <span className="badge-nochange">NO CHANGE</span>
                          )}
                        </td>
                        <td className="p-3 text-right font-mono text-muted-foreground">
                          {f.quarterPortfolioPct !== null
                            ? `${f.quarterPortfolioPct.toFixed(2)}%`
                            : "—"}
                        </td>
                        <td className="p-3 text-right font-mono">
                          {f.avgPrice === "N/A" ? "N/A" : `$${f.avgPrice}`}
                        </td>
                        <td className="p-3 text-right font-mono">{f.value}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
