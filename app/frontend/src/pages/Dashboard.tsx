import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { SlidersHorizontal } from "lucide-react";
import { Link } from "react-router";
import { learnItem } from "@/lib/routes";
import {
  getStocks,
  getHedgeFunds,
  parseValueString,
  formatPct,
  type EnrichedNQFiling,
} from "@/lib/dataService";
import { usePageMeta } from "@/hooks/usePageMeta";
import { LATEST_PAGE } from "@/lib/pageMeta";
import { useSortState, type SortDir } from "@/hooks/useSortState";
import { SortArrow } from "@/components/ui/SortArrow";
import { canonicalUrl } from "@/lib/seo";
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
import { QueryState } from "@/components/ui/QueryState";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { TableFrame } from "@/components/ui/TableFrame";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { StarredFilterToggle } from "@/components/StarredFilterToggle";
import { isoDaysBefore, toInitCap, matchesQuery } from "@/lib/utils";
import { useStarred } from "@/hooks/useStarred";
import { useEnrichedNQFilings } from "@/hooks/useEnrichedNQFilings";
import { useResearchState } from "@/hooks/useResearchState";

function IndustryLabel({ sector, industry }: { sector?: string; industry?: string }) {
  return (
    <span
      className="block truncate text-xs text-muted-foreground md:line-clamp-2 md:whitespace-normal md:leading-4"
      title={industry ?? sector}
    >
      {industry ?? sector ?? "—"}
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

const COUNTED_DELTA_TYPES = ["NEW", "INCREASE", "DECREASE", "CLOSED"] as const;
type CountedDeltaType = (typeof COUNTED_DELTA_TYPES)[number];

function isCountedDeltaType(t: EnrichedNQFiling["deltaType"]): t is CountedDeltaType {
  return COUNTED_DELTA_TYPES.some((c) => c === t);
}

const SORT_OPTIONS: readonly { value: SortField; label: string }[] = [
  { value: "date", label: "Published" },
  { value: "delta", label: "Shares Δ" },
  { value: "value", label: "Est. value" },
];

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
  const active = sortField === field;
  return (
    <th
      scope="col"
      aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
      className={`p-0 ${align === "right" ? "text-right" : "text-left"}`}
    >
      <button
        type="button"
        onClick={() => onSort(field)}
        className={`h-full w-full px-2 py-3 whitespace-nowrap hover:text-foreground hover:bg-muted ${
          align === "right" ? "text-right" : "text-left"
        }`}
      >
        {label}
        <SortArrow active={active} direction={sortDir} />
      </button>
    </th>
  );
}

/** A position's disclosure and valuation context on narrow screens. */
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

      <div className="mt-1 flex items-center gap-2 flex-wrap text-xs text-muted-foreground">
        <IndustryLabel sector={sector} industry={industry} />
        <span>
          Published <time dateTime={f.filingDate}>{f.filingDate || "—"}</time>
        </span>
        <span>
          Position as of <time dateTime={f.date}>{f.date || "—"}</time>
        </span>
      </div>

      <div className="mt-2">
        <FundCell fundName={f.fund} />
      </div>

      <div className="status-line mt-2 flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
        <span>
          <span className="k">Est. value:</span> {f.value}
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
          <span className="k">Reference price:</span>{" "}
          {f.avgPrice === "N/A" ? "N/A" : `$${f.avgPrice}`}
        </span>
      </div>
    </li>
  );
}

export default function Dashboard() {
  usePageMeta({
    title: LATEST_PAGE.title,
    description: LATEST_PAGE.description,
    canonical: canonicalUrl(LATEST_PAGE.path),
  });

  const [search, setSearch] = useResearchState("search", "");
  const [fundFilter, setFundFilter] = useResearchState("fund", "all");
  const [typeFilters, setTypeFilters] = useResearchState<Set<string>>("changes", () => new Set());
  const [daysBackPick, setDaysBackPick] = useResearchState<string | null>("period", null);
  const [filtersOpen, setFiltersOpen] = useResearchState("filtersOpen", false);
  const {
    sortKey: sortField,
    sortDir,
    toggleSort,
  } = useSortState<SortField>("date", "desc", "filings");
  const [today] = useState(() => new Date());
  const { starred: starredStocks } = useStarred("stock");
  const { starred: starredFunds } = useStarred("fund");
  const [filterStarredStocks, setFilterStarredStocks] = useResearchState("starredStocks", false);
  const [filterStarredFunds, setFilterStarredFunds] = useResearchState("starredFunds", false);

  const { data: filings = [], isLoading, isError, error } = useEnrichedNQFilings();

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

  const autoDaysBack = useMemo(() => {
    if (filings.length === 0) return "30";
    const cutoffStr = isoDaysBefore(today, 30);
    return filings.some((f) => f.filingDate >= cutoffStr) ? "30" : "9999";
  }, [filings, today]);
  const daysBack = daysBackPick ?? autoDaysBack;

  // Period + fund scope, shared by the counters and the table so they never
  // disagree. The type toggles, starred filters and search apply after.
  const scoped = useMemo(() => {
    const cutoffStr = isoDaysBefore(today, parseInt(daysBack));
    return filings.filter(
      (f) => f.filingDate >= cutoffStr && (fundFilter === "all" || f.fund === fundFilter),
    );
  }, [filings, daysBack, fundFilter, today]);

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
        cmp = a.filingDate.localeCompare(b.filingDate) || a.date.localeCompare(b.date);
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
      if (isCountedDeltaType(f.deltaType)) c[f.deltaType]++;
    }
    return c;
  }, [scoped]);

  const totalCount = FILING_TYPES.reduce((s, t) => s + counts[t], 0);
  const periodLabel = daysBack === "30" ? "published in the last 30 days" : "all publication dates";

  return (
    <div className="space-y-4 max-w-screen-2xl">
      <div>
        <h1 className="page-title">Latest Filings</h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-3xl">
          Latest saved 13D/G and Form 4 disclosure per position, by publication date. Changes are
          measured against each fund’s latest 13F.{" "}
          <Link
            to={learnItem("how-to-read-filing-metrics")}
            className="text-primary-text hover:underline underline-offset-4"
          >
            How to read these figures
          </Link>
        </p>
      </div>

      {!isLoading && filings.length > 0 && (
        <div>
          <p className="status-line mb-1">
            <span className="k">Positions {periodLabel}:</span> {totalCount}
            {fundFilter !== "all" && (
              <>
                {" "}
                <span aria-hidden="true">·</span> <span className="k">Fund:</span>{" "}
                {fundFilter.replace(/_/g, " ")}
              </>
            )}
          </p>
          <div
            className="grid grid-cols-4 gap-px overflow-hidden rounded-lg border border-border bg-border"
            role="group"
            aria-label="Filter by position change"
          >
            {FILING_TYPES.map((type) => {
              const isActive = typeFilters.has(type);
              const { label, text } = STAT_META[type];
              const count = counts[type];
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
                  className={`min-w-0 px-2 py-3 text-left transition-colors sm:px-4 ${
                    isActive
                      ? "bg-muted ring-2 ring-inset ring-primary"
                      : "bg-card hover:bg-muted/60"
                  }`}
                >
                  <span className="block text-[11px] text-muted-foreground sm:text-xs">
                    {label}
                  </span>
                  <span className="mt-1 flex items-baseline justify-between gap-1">
                    <span
                      className={`text-2xl font-semibold tabular-nums leading-none sm:text-3xl ${count > 0 ? text : "text-foreground"}`}
                    >
                      {count}
                    </span>
                    <span className="hidden text-xs tabular-nums text-muted-foreground sm:inline">
                      {totalCount > 0 ? Math.round((count / totalCount) * 100) : 0}%
                    </span>
                  </span>
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

      <div className="flex flex-wrap items-center gap-2">
        <SearchInput
          label="Search fund, manager, ticker, company"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          wrapperClassName="w-full sm:w-64"
        />
        <SegmentedControl
          value={daysBack}
          onValueChange={setDaysBackPick}
          aria-label="Publication period"
          options={[
            { value: "30", label: "Last 30 days" },
            { value: "9999", label: "All" },
          ]}
        />
        <button
          type="button"
          aria-expanded={filtersOpen}
          aria-controls="filing-filters"
          onClick={() => setFiltersOpen((open) => !open)}
          className="md:hidden inline-flex min-h-9 items-center gap-1.5 rounded-md border border-border px-3 text-xs hover:bg-muted"
        >
          <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
          Filters{fundFilter !== "all" ? " · 1" : ""}
        </button>
        <div
          id="filing-filters"
          className={`${filtersOpen ? "flex" : "hidden md:flex"} w-full flex-wrap items-center gap-2 md:w-auto`}
        >
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
          <div className="md:hidden flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Sort:</span>
            <SegmentedControl
              size="sm"
              aria-label="Sort filings"
              value={sortField}
              onValueChange={toggleSort}
              options={SORT_OPTIONS.map((option) => ({
                value: option.value,
                title: option.label,
                label: (
                  <span className="inline-flex items-center">
                    {option.label}
                    <SortArrow active={sortField === option.value} direction={sortDir} />
                  </span>
                ),
              }))}
            />
          </div>
        </div>
      </div>

      {isError ? (
        <QueryState isError error={error} title="Could not load filings" />
      ) : isLoading ? (
        <LoadingState message="Loading and enriching filings…" className="surface" />
      ) : (
        <>
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
          <div className="surface @container hidden md:block">
            <TableFrame label={`Latest filings, ${periodLabel}`}>
              <table
                className="w-full min-w-[960px] table-fixed text-sm"
                aria-label={`Latest filings, ${periodLabel}`}
              >
                <colgroup>
                  {/* Keep numeric/date columns stable; split remaining frame space 40/30/30. */}
                  <col className="w-[100px]" />
                  <col className="w-[max(172px,calc(40cqw_-_212px))]" />
                  <col className="w-[max(129px,calc(30cqw_-_159px))]" />
                  <col className="w-[max(129px,calc(30cqw_-_159px))]" />
                  <col className="w-[130px]" />
                  <col className="w-[84px]" />
                  <col className="w-[96px]" />
                  <col className="w-[120px]" />
                </colgroup>
                <thead>
                  <tr className="whitespace-nowrap">
                    <th scope="col" className="text-left px-2 py-3">
                      Ticker
                    </th>
                    <th scope="col" className="text-left px-2 py-3">
                      Company
                    </th>
                    <th scope="col" className="text-left px-2 py-3">
                      Industry
                    </th>
                    <th scope="col" className="text-left px-2 py-3">
                      Fund
                    </th>
                    <SortableTh
                      field="date"
                      label="Published / As of"
                      align="left"
                      sortField={sortField}
                      sortDir={sortDir}
                      onSort={toggleSort}
                    />
                    <SortableTh
                      field="delta"
                      label="Shares Δ"
                      align="right"
                      sortField={sortField}
                      sortDir={sortDir}
                      onSort={toggleSort}
                    />
                    <th scope="col" className="text-right px-2 py-3">
                      <span className="inline-flex items-center gap-1">
                        Portfolio %
                        <InfoTooltip text="Weight in the fund's latest 13F. ~ marks an estimated weight for a position absent from that baseline." />
                      </span>
                    </th>
                    <SortableTh
                      field="value"
                      label="Est. value"
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
                      <td colSpan={8} className="p-8 text-center text-muted-foreground">
                        No filings match your filters.
                      </td>
                    </tr>
                  ) : (
                    filtered.map((f, i) => (
                      <tr
                        key={`${f.cusip}-${f.fund}-${f.date}-${f.deltaType}-${f.shares ?? i}`}
                        className="data-table-row h-16"
                      >
                        <td className="px-2 py-3">
                          <TickerLink ticker={f.ticker} />
                        </td>
                        <td className="px-2 py-3">
                          <CompanyLink
                            ticker={f.ticker}
                            company={toInitCap(f.company)}
                            className="line-clamp-2 whitespace-normal leading-4"
                            showStar
                          />
                        </td>
                        <td className="px-2 py-3">
                          <IndustryLabel
                            sector={tickerMeta.get(f.ticker)?.sector}
                            industry={tickerMeta.get(f.ticker)?.industry}
                          />
                        </td>
                        <td className="px-2 py-3">
                          <FundCell
                            fundName={f.fund}
                            className="[&>span>span:first-child]:line-clamp-2 [&>span>span:first-child]:whitespace-normal [&>span>span:first-child]:leading-4"
                          />
                        </td>
                        <td className="px-2 py-3 text-muted-foreground whitespace-nowrap">
                          <time dateTime={f.filingDate} className="block text-foreground">
                            {f.filingDate || "—"}
                          </time>
                          <span className="block text-xs">
                            As of <time dateTime={f.date}>{f.date || "—"}</time>
                          </span>
                        </td>
                        <td className="px-2 py-3 text-right font-mono whitespace-nowrap">
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
                          className="px-2 py-3 text-right font-mono text-muted-foreground whitespace-nowrap"
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
                        <td className="px-2 py-3 text-right font-mono whitespace-nowrap">
                          <span className="block">{f.value}</span>
                          <span className="block text-xs text-muted-foreground">
                            Ref. price {f.avgPrice === "N/A" ? "—" : `$${f.avgPrice}`}
                          </span>
                        </td>
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
