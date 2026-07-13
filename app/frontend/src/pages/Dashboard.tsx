import { useState, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getEnrichedNQFilings,
  getStocks,
  getHedgeFunds,
  parseValueString,
  clearCache,
  formatPct,
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
import { SearchInput } from "@/components/ui/SearchInput";
import { LoadingState } from "@/components/ui/LoadingState";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { StarredFilterToggle } from "@/components/StarredFilterToggle";
import {
  ArrowUpRight,
  ArrowDownRight,
  Plus,
  X,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  FileText,
  type LucideIcon,
} from "lucide-react";
import { toInitCap, matchesQuery } from "@/lib/utils";
import { useStarred } from "@/hooks/useStarred";

/**
 * Inline sector pill for the Latest Filings table. Lives as a top-level
 * component (not an IIFE inside the row) so React Compiler can optimise it.
 */
function SectorPill({ sector, industry }: { sector?: string; industry?: string }) {
  if (!sector) {
    return <span className="text-faint">—</span>;
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

const FILING_TYPES = ["NEW", "INCREASE", "DECREASE", "CLOSED"] as const;
type FilingType = (typeof FILING_TYPES)[number];

const STAT_META: Record<
  FilingType,
  { label: string; icon: LucideIcon; bg: string; text: string; active: string }
> = {
  NEW: {
    label: "New",
    icon: Plus,
    bg: "bg-primary",
    text: "text-primary",
    active: "ring-primary/40 border-primary/50 bg-primary/[0.06]",
  },
  INCREASE: {
    label: "Increased",
    icon: ArrowUpRight,
    bg: "bg-positive",
    text: "text-positive",
    active: "ring-positive/40 border-positive/50 bg-positive/[0.06]",
  },
  DECREASE: {
    label: "Decreased",
    icon: ArrowDownRight,
    bg: "bg-negative",
    text: "text-negative",
    active: "ring-negative/40 border-negative/50 bg-negative/[0.06]",
  },
  CLOSED: {
    label: "Closed",
    icon: X,
    bg: "bg-closed",
    text: "text-closed",
    active: "ring-closed/40 border-closed/50 bg-closed/[0.06]",
  },
};

function formatDelta(f: EnrichedNQFiling): { text: string; className: string; sortValue: number } {
  if (f.deltaType === "CLOSED")
    return { text: "CLOSE", className: "text-closed", sortValue: -Infinity };
  if (f.deltaType === "NEW")
    return { text: "NEW", className: "text-positive", sortValue: Infinity };
  if (f.deltaType === "NO CHANGE")
    return { text: "+0%", className: "text-muted-foreground", sortValue: 0 };
  if (f.deltaPct !== null) {
    const cls = f.deltaPct > 0 ? "text-positive" : "text-negative";
    return { text: formatPct(f.deltaPct, true), className: cls, sortValue: f.deltaPct };
  }
  return { text: "NEW", className: "text-positive", sortValue: Infinity };
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

/**
 * Mobile equivalent of one table row. The 9-column table is unreadable on a
 * phone, so below `md` each filing becomes a self-contained card: ticker +
 * delta on the headline row, company + sector + date, the fund, and a compact
 * three-up stats footer. The left accent mirrors the table's row border.
 */
function FilingCard({
  f,
  sector,
  industry,
}: {
  f: EnrichedNQFiling;
  sector?: string;
  industry?: string;
}) {
  const borderClass =
    f.deltaType === "CLOSED" || f.deltaType === "DECREASE"
      ? "border-l-2 border-l-negative"
      : f.deltaType === "NEW" || f.deltaType === "INCREASE"
        ? "border-l-2 border-l-positive"
        : "border-l-2 border-l-muted";

  return (
    <div className={`surface p-3.5 ${borderClass}`}>
      <div className="flex items-start justify-between gap-3">
        <TickerLink ticker={f.ticker} />
        <span className="shrink-0 font-mono">
          {f.deltaType === "NEW" ? (
            <span className="badge-new">NEW</span>
          ) : f.deltaType === "CLOSED" ? (
            <span className="badge-closed">CLOSE</span>
          ) : f.deltaPct !== null ? (
            <Delta value={f.deltaPct} mode="percent" />
          ) : (
            <span className="badge-nochange">NO CHANGE</span>
          )}
        </span>
      </div>

      <div className="mt-2 flex items-center gap-2 flex-wrap text-xs">
        <CompanyLink ticker={f.ticker} company={toInitCap(f.company)} showStar />
      </div>

      <div className="mt-2 flex items-center gap-2 flex-wrap text-xs">
        <SectorPill sector={sector} industry={industry} />
        <span className="text-muted-foreground whitespace-nowrap">{f.date}</span>
      </div>

      <div className="mt-3 pt-3 border-t border-border/60">
        <FundCell fundName={f.fund} />
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="metric-label">Value</div>
          <div className="font-mono text-sm text-foreground mt-0.5">{f.value}</div>
        </div>
        <div>
          <div className="metric-label">Port. %</div>
          <div className="font-mono text-sm text-muted-foreground mt-0.5">
            {f.quarterPortfolioPct !== null
              ? `${f.quarterPortfolioPct.toFixed(2)}%`
              : f.estimatedPortfolioPct !== null
                ? `~${f.estimatedPortfolioPct.toFixed(2)}%`
                : "—"}
          </div>
        </div>
        <div>
          <div className="metric-label">Avg Px</div>
          <div className="font-mono text-sm text-muted-foreground mt-0.5">
            {f.avgPrice === "N/A" ? "N/A" : `$${f.avgPrice}`}
          </div>
        </div>
      </div>
    </div>
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

  const { data: filings = [], isLoading } = useQuery({
    queryKey: ["enrichedNQFilings"],
    queryFn: () => {
      clearCache("enriched_nq");
      return getEnrichedNQFilings();
    },
  });

  const { data: stocks = [] } = useQuery({ queryKey: ["stocks"], queryFn: getStocks });
  const { data: hedgeFunds = [] } = useQuery({
    queryKey: ["hedgeFunds"],
    queryFn: getHedgeFunds,
  });
  // Filings only carry the fund's file name, not its manager — map it so the
  // search box can match on manager too (parity with global search / fund grid).
  const managerByFund = useMemo(() => {
    const map = new Map<string, string>();
    for (const f of hedgeFunds) map.set(f.fund, f.manager);
    return map;
  }, [hedgeFunds]);

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
      if (!matchesQuery(search, f.ticker, f.fund, f.company, managerByFund.get(f.fund)))
        return false;
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
    managerByFund,
  ]);

  const counts = useMemo(() => {
    const c = { NEW: 0, INCREASE: 0, DECREASE: 0, CLOSED: 0 };
    for (const f of filings) {
      if (f.deltaType in c) c[f.deltaType as keyof typeof c]++;
    }
    return c;
  }, [filings]);

  const totalCount = FILING_TYPES.reduce((s, t) => s + counts[t], 0);

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div>
        <span className="eyebrow">Recent activity</span>
        <h1 className="page-title mt-1.5">
          <FileText className="page-title-icon" /> Latest Filings
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">
          Last 30 days 13D/G and Form 4 — latest filing per position, delta vs last 13F quarter
        </p>
      </div>

      {!isLoading && filings.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {FILING_TYPES.map((type) => {
            const isActive = typeFilters.has(type);
            const { label, icon: Icon, bg, text, active } = STAT_META[type];
            const count = counts[type];
            const share = totalCount > 0 ? Math.round((count / totalCount) * 100) : 0;
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
                aria-pressed={isActive}
                className={`surface flex flex-col gap-3 p-4 text-left transition-colors ${
                  isActive ? `ring-2 ${active}` : "hover:border-border"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="metric-label flex items-center gap-1.5">
                    <span className={`h-1.5 w-1.5 rounded-full ${bg}`} />
                    {label}
                  </span>
                  <Icon className="h-3.5 w-3.5 icon-faint" />
                </div>
                <div className="flex items-baseline justify-between gap-2">
                  <span className={`metric-value ${count > 0 ? text : "text-faint"}`}>{count}</span>
                  <span className="font-mono text-xs tabular-nums text-muted-foreground">
                    {share}%
                  </span>
                </div>
                <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={`h-full rounded-full ${count > 0 ? bg : "bg-transparent"}`}
                    style={{ width: `${share}%` }}
                  />
                </div>
              </button>
            );
          })}
        </div>
      )}

      <StarredFilterToggle
        fundsCount={starredFunds.size}
        stocksCount={starredStocks.size}
        filterFunds={filterStarredFunds}
        filterStocks={filterStarredStocks}
        onToggleFunds={() => setFilterStarredFunds((v) => !v)}
        onToggleStocks={() => setFilterStarredStocks((v) => !v)}
      />

      <div className="flex flex-col sm:flex-row sm:flex-wrap gap-3">
        <SearchInput
          label="Search fund, manager, ticker, company"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          wrapperClassName="w-full sm:w-64"
        />
        <Select value={fundFilter} onValueChange={setFundFilter}>
          <SelectTrigger className="w-full sm:w-48 bg-card border-border">
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
        <SegmentedControl
          value={daysBack}
          onValueChange={setDaysBackPick}
          options={[
            { value: "30", label: "Last 30 days" },
            { value: "9999", label: "All" },
          ]}
        />
      </div>

      {isLoading ? (
        <LoadingState message="Loading and enriching filings…" className="surface" />
      ) : (
        <>
          {/* Mobile: compact sort bar (the table's clickable headers are gone here) */}
          <div className="md:hidden flex items-center gap-2 overflow-x-auto">
            <span className="text-xs text-muted-foreground shrink-0">Sort</span>
            {(
              [
                ["date", "Date"],
                ["delta", "Delta"],
                ["value", "Value"],
              ] as const
            ).map(([field, label]) => {
              const isActive = sortField === field;
              return (
                <button
                  key={field}
                  onClick={() => toggleSort(field)}
                  aria-pressed={isActive}
                  className={`inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors shrink-0 ${
                    isActive
                      ? "border-primary/50 bg-primary/10 text-primary"
                      : "border-border bg-card text-muted-foreground"
                  }`}
                >
                  {label}
                  {isActive &&
                    (sortDir === "asc" ? (
                      <ArrowUp className="h-3 w-3" />
                    ) : (
                      <ArrowDown className="h-3 w-3" />
                    ))}
                </button>
              );
            })}
          </div>

          {/* Mobile: card list */}
          <div className="md:hidden space-y-3">
            {filtered.length === 0 ? (
              <div className="surface p-8 text-center text-muted-foreground">
                No filings match your filters.
              </div>
            ) : (
              filtered.map((f, i) => (
                <FilingCard
                  key={`${f.cusip}-${f.fund}-${f.date}-${f.deltaType}-${f.shares ?? i}`}
                  f={f}
                  sector={tickerMeta.get(f.ticker)?.sector}
                  industry={tickerMeta.get(f.ticker)?.industry}
                />
              ))
            )}
          </div>

          {/* Desktop: full data table */}
          <div className="surface overflow-hidden hidden md:block">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-[10px] text-muted-foreground uppercase tracking-wider whitespace-nowrap">
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
                        Delta{" "}
                        <SortIcon field="delta" currentField={sortField} direction={sortDir} />
                      </span>
                    </th>
                    <th
                      className="text-right p-3 font-medium"
                      title="Position weight in the fund's last 13F portfolio; ~ marks an estimated weight for positions known only from a 13D/G or Form 4 filing"
                    >
                      Portfolio %
                    </th>
                    <th className="text-right p-3 font-medium">Avg Price</th>
                    <th
                      className="text-right p-3 font-medium cursor-pointer select-none hover:text-foreground transition-colors"
                      onClick={() => toggleSort("value")}
                    >
                      <span className="inline-flex items-center justify-end">
                        Value{" "}
                        <SortIcon field="value" currentField={sortField} direction={sortDir} />
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
                          <td
                            className="p-3 text-right font-mono text-muted-foreground"
                            title={
                              f.quarterPortfolioPct === null && f.estimatedPortfolioPct !== null
                                ? "Estimated weight over the fund's merged portfolio (new position)"
                                : undefined
                            }
                          >
                            {f.quarterPortfolioPct !== null
                              ? `${f.quarterPortfolioPct.toFixed(2)}%`
                              : f.estimatedPortfolioPct !== null
                                ? `~${f.estimatedPortfolioPct.toFixed(2)}%`
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
          </div>
        </>
      )}
    </div>
  );
}
