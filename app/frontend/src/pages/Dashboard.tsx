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
import { usePageMeta, pageTitle } from "@/hooks/usePageMeta";
import { ROUTES } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";
import { getSectorStyle, sectorPillStyle, SECTOR_PILL } from "@/lib/sectorStyle";
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
import { TableFrame } from "@/components/ui/TableFrame";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { StarredFilterToggle } from "@/components/StarredFilterToggle";
import { toInitCap, matchesQuery } from "@/lib/utils";
import { useStarred } from "@/hooks/useStarred";
import { ArrowDown, ArrowUp } from "lucide-react";

/** Sector tag: a tinted pill in the sector's own colour, applied inline. */
function SectorPill({ sector, industry }: { sector?: string; industry?: string }) {
  if (!sector) {
    return <span className="text-faint">—</span>;
  }
  const style = getSectorStyle(sector);
  const Icon = style.icon;
  return (
    <span className={SECTOR_PILL} style={sectorPillStyle(style)} title={industry ?? sector}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {sector}
    </span>
  );
}

const FILING_TYPES = ["NEW", "INCREASE", "DECREASE", "CLOSED"] as const;
type FilingType = (typeof FILING_TYPES)[number];

const STAT_META: Record<FilingType, { label: string; text: string }> = {
  NEW: { label: "New", text: "text-positive" },
  INCREASE: { label: "Increased", text: "text-positive" },
  DECREASE: { label: "Decreased", text: "text-negative" },
  CLOSED: { label: "Closed", text: "text-closed" },
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

type SortField = "date" | "delta" | "value";
type SortDir = "asc" | "desc";

const SORT_OPTIONS: readonly { value: SortField; label: string }[] = [
  { value: "date", label: "Date" },
  { value: "delta", label: "Delta" },
  { value: "value", label: "Value" },
];

/** The one sort-direction grammar on this page: a lucide arrow, never a glyph. */
function SortArrow({
  field,
  currentField,
  direction,
}: {
  field: SortField;
  currentField: SortField;
  direction: SortDir;
}) {
  if (currentField !== field) return null;
  const Icon = direction === "asc" ? ArrowUp : ArrowDown;
  return <Icon className="ml-1 inline-block h-3 w-3 align-[-1px]" aria-hidden="true" />;
}

function ariaSort(field: SortField, currentField: SortField, direction: SortDir) {
  if (currentField !== field) return "none";
  return direction === "asc" ? "ascending" : "descending";
}

/** Sortable column header: the button carries the click, the th carries aria-sort. */
function SortableTh({
  field,
  label,
  align,
  sortField,
  sortDir,
  onSort,
}: {
  field: SortField;
  label: string;
  align: "left" | "right";
  sortField: SortField;
  sortDir: SortDir;
  onSort: (field: SortField) => void;
}) {
  return (
    <th
      scope="col"
      aria-sort={ariaSort(field, sortField, sortDir)}
      className={`p-0 ${align === "right" ? "text-right" : "text-left"}`}
    >
      <button
        type="button"
        onClick={() => onSort(field)}
        className={`h-full w-full p-3 whitespace-nowrap hover:text-foreground hover:bg-muted ${
          align === "right" ? "text-right" : "text-left"
        }`}
      >
        {label}
        <SortArrow field={field} currentField={sortField} direction={sortDir} />
      </button>
    </th>
  );
}

/** Mobile row for one filing: the 9-column table does not fit a phone. */
function FilingCard({
  f,
  sector,
  industry,
}: {
  f: EnrichedNQFiling;
  sector?: string;
  industry?: string;
}) {
  return (
    <li className="border-b border-border py-2">
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

      <div className="mt-1 flex items-center gap-2 flex-wrap text-xs">
        <CompanyLink ticker={f.ticker} company={toInitCap(f.company)} showStar />
      </div>

      <div className="mt-1 flex items-center gap-2 flex-wrap text-xs">
        <SectorPill sector={sector} industry={industry} />
        <span className="text-muted-foreground whitespace-nowrap">{f.date}</span>
      </div>

      <div className="mt-2">
        <FundCell fundName={f.fund} />
      </div>

      <div className="status-line mt-2 flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
        <span>
          <span className="k">Value:</span> {f.value}
        </span>
        <span aria-hidden="true">·</span>
        <span>
          <span className="k">Port. %:</span>{" "}
          {f.quarterPortfolioPct !== null
            ? `${f.quarterPortfolioPct.toFixed(2)}%`
            : f.estimatedPortfolioPct !== null
              ? `~${f.estimatedPortfolioPct.toFixed(2)}%`
              : "—"}
        </span>
        <span aria-hidden="true">·</span>
        <span>
          <span className="k">Avg Px:</span> {f.avgPrice === "N/A" ? "N/A" : `$${f.avgPrice}`}
        </span>
      </div>
    </li>
  );
}

export default function Dashboard() {
  usePageMeta({
    title: pageTitle("Latest Filings"),
    description:
      "The newest SEC filings from every tracked hedge fund — 13F, 13D/G, Form 4 and N-Q — with position deltas, in one board.",
    canonical: canonicalUrl(ROUTES.latest),
  });

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

  // Period + fund scope, shared by the counters and the table so they never
  // disagree. The type toggles, starred filters and search apply after.
  const scoped = useMemo(() => {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - parseInt(daysBack));
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    return filings.filter(
      (f) => f.date >= cutoffStr && (fundFilter === "all" || f.fund === fundFilter),
    );
  }, [filings, daysBack, fundFilter]);

  const filtered = useMemo(() => {
    let rows = scoped.filter((f) => {
      if (typeFilters.size > 0 && !typeFilters.has(f.deltaType)) return false;
      if (filterStarredFunds && starredFunds.size > 0 && !starredFunds.has(f.fund)) return false;
      if (filterStarredStocks && starredStocks.size > 0 && !starredStocks.has(f.ticker))
        return false;
      if (!matchesQuery(search, f.ticker, f.fund, f.company, managerByFund.get(f.fund)))
        return false;
      return true;
    });

    rows = [...rows].sort((a, b) => {
      let cmp = 0;
      if (sortField === "date") {
        cmp = a.date.localeCompare(b.date);
      } else if (sortField === "delta") {
        cmp = formatDelta(a).sortValue - formatDelta(b).sortValue;
      } else {
        cmp = parseValueString(a.value) - parseValueString(b.value);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

    return rows;
  }, [
    scoped,
    typeFilters,
    search,
    sortField,
    sortDir,
    filterStarredFunds,
    filterStarredStocks,
    starredFunds,
    starredStocks,
    managerByFund,
  ]);

  const counts = useMemo(() => {
    const c = { NEW: 0, INCREASE: 0, DECREASE: 0, CLOSED: 0 };
    for (const f of scoped) {
      if (f.deltaType in c) c[f.deltaType as keyof typeof c]++;
    }
    return c;
  }, [scoped]);

  const totalCount = FILING_TYPES.reduce((s, t) => s + counts[t], 0);
  const periodLabel = daysBack === "30" ? "last 30 days" : "all filings";

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div>
        <h1 className="page-title">Latest Filings</h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">
          13D/G and Form 4, latest filing per position, delta vs last 13F quarter
        </p>
      </div>

      {!isLoading && filings.length > 0 && (
        <div>
          <p className="status-line mb-1">
            <span className="k">Filings, {periodLabel}:</span> {totalCount}
            {fundFilter !== "all" && (
              <>
                {" "}
                <span aria-hidden="true">·</span> <span className="k">Fund:</span>{" "}
                {fundFilter.replace(/_/g, " ")}
              </>
            )}
          </p>
          <div
            className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border border border-border"
            role="group"
            aria-label="Filter by filing type"
          >
            {FILING_TYPES.map((type) => {
              const isActive = typeFilters.has(type);
              const { label, text } = STAT_META[type];
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
                  type="button"
                  onClick={toggle}
                  aria-pressed={isActive}
                  className={`relative p-3 text-left transition-colors ${
                    isActive ? "bg-muted" : "bg-card hover:bg-muted/60"
                  }`}
                >
                  <span className="metric-label block">{label}</span>
                  <span className="flex items-baseline justify-between gap-2">
                    <span className={`metric-value ${count > 0 ? text : "text-faint"}`}>
                      {count}
                    </span>
                    <span className="text-xs tabular-nums text-muted-foreground">{share}%</span>
                  </span>
                  {/* Pressed state: the 2px primary bar, the same signal the nav uses. */}
                  {isActive && (
                    <span
                      aria-hidden="true"
                      className="absolute inset-x-0 bottom-0 h-0.5 bg-primary"
                    />
                  )}
                </button>
              );
            })}
          </div>
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
          <SelectTrigger aria-label="Fund" className="w-full sm:w-48 bg-card border-border">
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
          {/* Mobile: sort strip (the table's sortable headers are gone here) */}
          <div className="md:hidden flex items-center gap-2 overflow-x-auto">
            <span className="status-line shrink-0">
              <span className="k">Sort:</span>
            </span>
            <SegmentedControl
              size="sm"
              aria-label="Sort filings"
              value={sortField}
              onValueChange={toggleSort}
              options={SORT_OPTIONS.map((o) => ({
                value: o.value,
                title: o.label,
                label: (
                  <span className="inline-flex items-center">
                    {o.label}
                    <SortArrow field={o.value} currentField={sortField} direction={sortDir} />
                  </span>
                ),
              }))}
            />
          </div>

          {/* Mobile: row list */}
          <div className="md:hidden">
            {filtered.length === 0 ? (
              <div className="surface p-8 text-center text-muted-foreground">
                No filings match your filters.
              </div>
            ) : (
              <ul className="border-t border-border">
                {filtered.map((f, i) => (
                  <FilingCard
                    key={`${f.cusip}-${f.fund}-${f.date}-${f.deltaType}-${f.shares ?? i}`}
                    f={f}
                    sector={tickerMeta.get(f.ticker)?.sector}
                    industry={tickerMeta.get(f.ticker)?.industry}
                  />
                ))}
              </ul>
            )}
          </div>

          {/* Desktop: full data table */}
          <div className="surface hidden md:block">
            <TableFrame label={`Latest filings, ${periodLabel}`}>
              <table className="w-full text-sm" aria-label={`Latest filings, ${periodLabel}`}>
                <thead>
                  <tr className="whitespace-nowrap">
                    <th scope="col" className="text-left p-3">
                      Ticker
                    </th>
                    <th scope="col" className="text-left p-3">
                      Company
                    </th>
                    <th scope="col" className="text-left p-3">
                      Sector
                    </th>
                    <th scope="col" className="text-left p-3">
                      Fund
                    </th>
                    <SortableTh
                      field="date"
                      label="Date"
                      align="left"
                      sortField={sortField}
                      sortDir={sortDir}
                      onSort={toggleSort}
                    />
                    <SortableTh
                      field="delta"
                      label="Delta"
                      align="right"
                      sortField={sortField}
                      sortDir={sortDir}
                      onSort={toggleSort}
                    />
                    <th
                      scope="col"
                      className="text-right p-3"
                      title="Position weight in the fund's last 13F portfolio; ~ marks an estimated weight for positions known only from a 13D/G or Form 4 filing"
                    >
                      Portfolio %
                    </th>
                    <th scope="col" className="text-right p-3">
                      Avg Price
                    </th>
                    <SortableTh
                      field="value"
                      label="Value"
                      align="right"
                      sortField={sortField}
                      sortDir={sortDir}
                      onSort={toggleSort}
                    />
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
                    filtered.map((f, i) => (
                      <tr
                        key={`${f.cusip}-${f.fund}-${f.date}-${f.deltaType}-${f.shares ?? i}`}
                        className="data-table-row"
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
                    ))
                  )}
                </tbody>
              </table>
            </TableFrame>
          </div>
        </>
      )}
    </div>
  );
}
