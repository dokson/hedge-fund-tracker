import { useState, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getEnrichedNQFilings, parseValueString, clearCache, type EnrichedNQFiling } from "@/lib/dataService";
import { TickerLink, FundLink } from "@/components/EntityLinks";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, ArrowUpRight, ArrowDownRight, Plus, X, Minus, ArrowUpDown, ArrowUp, ArrowDown, FileText, Check, Star, Users, Building2 } from "lucide-react";
import { toInitCap } from "@/lib/utils";
import { useStarred } from "@/hooks/useStarred";

function formatDelta(f: EnrichedNQFiling): { text: string; className: string; sortValue: number } {
  if (f.deltaType === "CLOSED") return { text: "CLOSE", className: "text-rose-700 dark:text-rose-400", sortValue: -Infinity };
  if (f.deltaType === "NEW") return { text: "NEW", className: "text-teal-700 dark:text-teal-400", sortValue: Infinity };
  if (f.deltaType === "NO CHANGE") return { text: "+0%", className: "text-muted-foreground", sortValue: 0 };
  if (f.deltaPct !== null) {
    const sign = f.deltaPct > 0 ? "+" : "";
    const cls = f.deltaPct > 0 ? "text-positive" : "text-negative";
    return { text: `${sign}${f.deltaPct.toFixed(1)}%`, className: cls, sortValue: f.deltaPct };
  }
  return { text: "NEW", className: "text-teal-700 dark:text-teal-400", sortValue: Infinity };
}

const DELTA_ICON: Record<string, typeof ArrowUpRight | null> = {
  NEW: Plus,
  INCREASE: ArrowUpRight,
  DECREASE: ArrowDownRight,
  CLOSED: X,
  "NO CHANGE": Minus,
  UNKNOWN: null,
};

type SortField = "date" | "delta" | "value" | null;
type SortDir = "asc" | "desc";

export default function Dashboard() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [fundFilter, setFundFilter] = useState("all");
  const [typeFilters, setTypeFilters] = useState<Set<string>>(new Set());
  const [daysBack, setDaysBack] = useState("30");
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

  const fundNames = useMemo(() => {
    const names = [...new Set(filings.map((f) => f.fund))];
    return names.sort();
  }, [filings]);

  const toggleSort = useCallback((field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  }, [sortField]);

  const filtered = useMemo(() => {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - parseInt(daysBack));
    const cutoffStr = cutoff.toISOString().slice(0, 10);

    let rows = filings.filter((f) => {
      if (f.date < cutoffStr) return false;
      if (fundFilter !== "all" && f.fund !== fundFilter) return false;
      if (typeFilters.size > 0 && !typeFilters.has(f.deltaType)) return false;
      if (filterStarredFunds && starredFunds.size > 0 && !starredFunds.has(f.fund)) return false;
      if (filterStarredStocks && starredStocks.size > 0 && !starredStocks.has(f.ticker)) return false;
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
  }, [filings, fundFilter, typeFilters, search, sortField, sortDir, daysBack, filterStarredFunds, filterStarredStocks, starredFunds, starredStocks]);

  const counts = useMemo(() => {
    const c = { NEW: 0, INCREASE: 0, DECREASE: 0, CLOSED: 0 };
    for (const f of filings) {
      if (f.deltaType in c) c[f.deltaType as keyof typeof c]++;
    }
    return c;
  }, [filings]);

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowUpDown className="h-3 w-3 ml-1 opacity-40" />;
    return sortDir === "asc"
      ? <ArrowUp className="h-3 w-3 ml-1 text-primary" />
      : <ArrowDown className="h-3 w-3 ml-1 text-primary" />;
  };

  return (
    <div className="space-y-5 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2"><FileText className="h-6 w-6" /> Latest Filings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Last 30 days 13D/G and Form 4 — latest filing per position, delta vs last 13F quarter
        </p>
      </div>

      {!isLoading && filings.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {(["NEW", "INCREASE", "DECREASE", "CLOSED"] as const).map((type) => {
            const isActive = typeFilters.has(type);
            const colorClasses = {
              NEW: { active: "bg-[hsl(217,91%,60%)]/15 text-[hsl(217,91%,60%)] border-[hsl(217,91%,60%)] ring-2 ring-[hsl(217,91%,60%)]/30 ring-offset-1 ring-offset-background", inactive: "bg-transparent text-muted-foreground border-border hover:border-[hsl(217,91%,60%)]/40 hover:text-[hsl(217,91%,60%)]" },
              INCREASE: { active: "bg-positive/15 text-positive border-positive ring-2 ring-positive/30 ring-offset-1 ring-offset-background", inactive: "bg-transparent text-muted-foreground border-border hover:border-positive/40 hover:text-positive" },
              DECREASE: { active: "bg-negative/15 text-negative border-negative ring-2 ring-negative/30 ring-offset-1 ring-offset-background", inactive: "bg-transparent text-muted-foreground border-border hover:border-negative/40 hover:text-negative" },
              CLOSED: { active: "bg-[hsl(0,62%,45%)]/15 text-[hsl(0,62%,45%)] border-[hsl(0,62%,45%)] ring-2 ring-[hsl(0,62%,45%)]/30 ring-offset-1 ring-offset-background", inactive: "bg-transparent text-muted-foreground border-border hover:border-[hsl(0,62%,45%)]/40 hover:text-[hsl(0,62%,45%)]" },
            }[type];
            const icon = { NEW: Plus, INCREASE: ArrowUpRight, DECREASE: ArrowDownRight, CLOSED: X }[type];
            const Icon = icon;
            const label = { NEW: "New", INCREASE: "Increased", DECREASE: "Decreased", CLOSED: "Closed" }[type];
            const toggle = () => setTypeFilters((prev) => {
              const next = new Set(prev);
              if (next.has(type)) next.delete(type); else next.add(type);
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
          <span className="text-xs text-muted-foreground flex items-center gap-1"><Star className="h-3 w-3" fill="currentColor" /> Consider Starred only:</span>
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
            <Badge variant="secondary" className="text-[9px] px-1.5 py-0 h-4 leading-none">{starredFunds.size}</Badge>
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
            <Badge variant="secondary" className="text-[9px] px-1.5 py-0 h-4 leading-none">{starredStocks.size}</Badge>
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
              <SelectItem key={name} value={name}>{name.replace(/_/g, " ")}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={daysBack} onValueChange={setDaysBack}>
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
                  <th
                    className="text-left p-3 font-medium cursor-pointer select-none hover:text-foreground transition-colors"
                    onClick={() => toggleSort("date")}
                  >
                    <span className="inline-flex items-center">Date <SortIcon field="date" /></span>
                  </th>
                  <th className="text-left p-3 font-medium">Fund</th>
                  <th className="text-left p-3 font-medium">Ticker</th>
                  <th className="text-left p-3 font-medium">Company</th>
                  <th
                    className="text-right p-3 font-medium cursor-pointer select-none hover:text-foreground transition-colors"
                    onClick={() => toggleSort("delta")}
                  >
                    <span className="inline-flex items-center justify-end">Delta <SortIcon field="delta" /></span>
                  </th>
                  <th className="text-right p-3 font-medium">Avg Price</th>
                  <th
                    className="text-right p-3 font-medium cursor-pointer select-none hover:text-foreground transition-colors"
                    onClick={() => toggleSort("value")}
                  >
                    <span className="inline-flex items-center justify-end">Value <SortIcon field="value" /></span>
                  </th>
                  <th className="text-right p-3 font-medium" title="Position weight in the fund's last 13F portfolio">
                    Portfolio %
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-8 text-center text-muted-foreground">
                      No filings match your filters.
                    </td>
                  </tr>
                ) : (
                  filtered.map((f, i) => {
                    const delta = formatDelta(f);
                    const DeltaIcon = DELTA_ICON[f.deltaType];
                    const borderClass =
                      f.deltaType === "CLOSED" || f.deltaType === "DECREASE"
                        ? "border-l-2 border-l-negative"
                        : f.deltaType === "NEW" || f.deltaType === "INCREASE"
                        ? "border-l-2 border-l-positive"
                        : "border-l-2 border-l-muted";

                    return (
                      <tr
                        key={`${f.cusip}-${f.fund}-${i}`}
                        className={`data-table-row ${borderClass}`}
                      >
                        <td className="p-3 text-muted-foreground whitespace-nowrap">{f.date}</td>
                        <td className="p-3">
                          <FundLink fundName={f.fund} className="text-sm" />
                        </td>
                        <td className="p-3">
                          <TickerLink ticker={f.ticker} />
                        </td>
                        <td className="p-3 max-w-[200px] truncate">
                          <span
                            className="ticker-link text-muted-foreground"
                            onClick={(e) => { e.stopPropagation(); navigate(`/stock/${f.ticker}`); }}
                          >
                            {toInitCap(f.company)}
                          </span>
                        </td>
                        <td className="p-3 text-right font-mono">
                          {f.deltaType === "NEW" ? (
                            <span className="badge-new">NEW</span>
                          ) : f.deltaType === "CLOSED" ? (
                            <span className="badge-closed">CLOSE</span>
                          ) : (
                            <span className={`inline-flex items-center gap-0.5 ${delta.className}`}>
                              {DeltaIcon && <DeltaIcon className="h-3 w-3" />}
                              {delta.text}
                            </span>
                          )}
                        </td>
                        <td className="p-3 text-right font-mono">
                          {f.avgPrice === "N/A" ? "N/A" : `$${f.avgPrice}`}
                        </td>
                        <td className="p-3 text-right font-mono">{f.value}</td>
                        <td className="p-3 text-right font-mono text-muted-foreground">
                          {f.quarterPortfolioPct !== null ? `${f.quarterPortfolioPct.toFixed(2)}%` : "—"}
                        </td>
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
