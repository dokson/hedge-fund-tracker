import { useState, useMemo, useEffect, useRef } from "react";
import { useSearchParams, Link } from "react-router";
import { skipToken, useQuery } from "@tanstack/react-query";
import {
  getQuarterFundList,
  formatValue,
  type NumericStockKey,
  type StockQuarterAnalysis,
} from "@/lib/dataService";
import { sortAnalysisRows } from "@/lib/analysisSort";
import { isQuarter, type Quarter } from "@/lib/quarters";
import { STRATEGY_BY_TAB, STRATEGY_DEFS_PERF_ORDER, isStrategyTab } from "@/lib/strategies";
import { learnItem, performanceFor } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";
import { usePageMeta } from "@/hooks/usePageMeta";
import { QUARTERLY_PAGE } from "@/lib/pageMeta";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { useSortState } from "@/hooks/useSortState";
import { useResearchState } from "@/hooks/useResearchState";
import { useQuarterAnalysis } from "@/hooks/useQuarterAnalysis";
import { TickerLink, CompanyLink } from "@/components/EntityLinks";
import { Delta } from "@/components/Delta";
import { SmartScoreBadge } from "@/components/SmartScoreBadge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { BarChart3, LineChart, ArrowUpRight, ArrowUp, ArrowDown } from "lucide-react";
import { AnalysisProgress } from "@/components/ui/AnalysisProgress";
import { QueryState } from "@/components/ui/QueryState";
import { TableFrame } from "@/components/ui/TableFrame";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { useStarred } from "@/hooks/useStarred";
import { StarredFilterToggle } from "@/components/StarredFilterToggle";

type SortKey = NumericStockKey;

type CellAlign = "left" | "center" | "right";

// Literal class lookup (a template like `text-${align}` is invisible to
// Tailwind's scanner). Values default to center so figures sit under their
// header label; the entity columns (Ticker/Company) stay left-aligned.
const ALIGN_TEXT: Record<CellAlign, string> = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
};
const ALIGN_FLEX: Record<CellAlign, string> = {
  left: "",
  center: "flex justify-center",
  right: "flex justify-end",
};

function SortableHeader({
  label,
  sortKey,
  currentKey,
  currentDir,
  onSort,
  align = "center",
  tooltip,
}: {
  label: string;
  sortKey: SortKey;
  currentKey: SortKey;
  currentDir: "asc" | "desc";
  onSort: (k: SortKey) => void;
  align?: CellAlign;
  tooltip?: string;
}) {
  const active = currentKey === sortKey;
  return (
    <th
      scope="col"
      aria-sort={active ? (currentDir === "desc" ? "descending" : "ascending") : "none"}
      className={`${ALIGN_TEXT[align]} px-3 py-2`}
    >
      <span className="inline-flex items-center gap-1">
        <button
          type="button"
          onClick={() => onSort(sortKey)}
          // min-w-6: a two-character label ("Δ%") left the button 18px wide,
          // under the 24px minimum (SC 2.5.8).
          className={`inline-flex min-w-6 items-center justify-center gap-1 h-7 hover:text-foreground ${active ? "text-foreground" : ""}`}
        >
          {label}
          {active &&
            (currentDir === "desc" ? (
              <ArrowDown aria-hidden="true" className="h-3 w-3 shrink-0" />
            ) : (
              <ArrowUp aria-hidden="true" className="h-3 w-3 shrink-0" />
            ))}
        </button>
        {tooltip && <InfoTooltip text={tooltip} />}
      </span>
    </th>
  );
}

function AnalysisTable({
  data,
  defaultSort,
  defaultDir = "desc",
  columns,
  defaultMinHolders = 0,
  defaultFilterInfinite = false,
  defaultLimit = 30,
  disableFilters = false,
  deltaSign,
}: {
  data: readonly StockQuarterAnalysis[];
  defaultSort: SortKey;
  defaultDir?: "asc" | "desc";
  columns: {
    key: SortKey;
    label: string;
    align?: CellAlign;
    format?: (v: number, row: StockQuarterAnalysis) => string;
    colorFn?: (v: number) => string;
    tooltip?: string;
    /** Render as Delta cell (icon + value) instead of plain colored text. */
    deltaMode?: "currency" | "percent";
    /** Full custom cell (e.g. the Smart Score badge); wins over format/deltaMode. */
    render?: (row: StockQuarterAnalysis) => React.ReactNode;
  }[];
  defaultMinHolders?: number;
  defaultFilterInfinite?: boolean;
  defaultLimit?: number;
  disableFilters?: boolean;
  /** Hard constraint: keep only positive / negative deltas (Increasing / Decreasing). */
  deltaSign?: "positive" | "negative";
}) {
  const researchKey = `question:${defaultSort}`;
  const { sortKey, sortDir, toggleSort, setSort } = useSortState<SortKey>(
    defaultSort,
    defaultDir,
    researchKey,
  );
  const [minHolders, setMinHolders] = useResearchState(
    `${researchKey}:minHolders`,
    defaultMinHolders,
  );
  const [filterInfinite, setFilterInfinite] = useResearchState(
    `${researchKey}:excludeNew`,
    defaultFilterInfinite,
  );
  const [limit, setLimit] = useResearchState(`${researchKey}:limit`, defaultLimit);

  const filtered = useMemo(() => {
    let arr = disableFilters ? data : data.filter((s) => s.holderCount >= minHolders);
    if (!disableFilters && filterInfinite) arr = arr.filter((s) => isFinite(s.delta));
    // Sign constraint always applies, on the strategy's ranking metric (defaultSort) —
    // it defines the Increasing/Decreasing screens.
    if (deltaSign === "positive") arr = arr.filter((s) => (s[defaultSort] ?? NaN) > 0);
    else if (deltaSign === "negative") arr = arr.filter((s) => (s[defaultSort] ?? NaN) < 0);
    return arr;
  }, [data, minHolders, filterInfinite, disableFilters, deltaSign, defaultSort]);

  const sorted = useMemo(() => {
    const arr = sortAnalysisRows(filtered, sortKey, sortDir);
    return disableFilters ? arr : arr.slice(0, limit);
  }, [filtered, sortKey, sortDir, limit, disableFilters]);

  // The headline follows the actual ranking, including a restored custom sort.
  const headlineColumn = columns.find((c) => c.key === sortKey);
  const metricColumns = columns.filter((c) => c.key !== sortKey);
  const customRanking = sortKey !== defaultSort || sortDir !== defaultDir;

  return (
    <div className="space-y-3">
      {/* Filter controls */}
      <div
        className={`flex flex-wrap items-center gap-x-3 gap-y-2 text-sm ${disableFilters ? "opacity-40 pointer-events-none" : ""}`}
      >
        <div className="flex items-center gap-2">
          <Label htmlFor="minHolders" className="text-xs text-muted-foreground whitespace-nowrap">
            Min Holders
          </Label>
          <div className="flex h-9 items-center rounded-md border border-input bg-background">
            <button
              type="button"
              aria-label="Decrease minimum holders"
              onClick={() => setMinHolders(Math.max(0, minHolders - 1))}
              className="w-9 h-full text-muted-foreground hover:text-foreground hover:bg-muted transition-colors text-sm"
            >
              −
            </button>
            <Input
              id="minHolders"
              type="number"
              min={0}
              value={minHolders}
              onChange={(e) => setMinHolders(parseInt(e.target.value) || 0)}
              className="w-10 h-full border-0 bg-transparent text-xs text-center p-0"
            />
            <button
              type="button"
              aria-label="Increase minimum holders"
              onClick={() => setMinHolders(minHolders + 1)}
              className="w-9 h-full text-muted-foreground hover:text-foreground hover:bg-muted transition-colors text-sm"
            >
              +
            </button>
          </div>
        </div>
        {/* The whole label is the target, not the 36x20 switch: 20px is under
            the 24px minimum and the next filter group is 8px away, so the
            spacing exception does not rescue it either (SC 2.5.8). */}
        <Label
          htmlFor="excludeInf"
          className="flex h-9 cursor-pointer items-center gap-2 text-xs text-muted-foreground whitespace-nowrap"
        >
          Exclude NEW
          <Switch id="excludeInf" checked={filterInfinite} onCheckedChange={setFilterInfinite} />
        </Label>
        <div className="flex h-9 items-center gap-2">
          <Label htmlFor="limit" className="text-xs text-muted-foreground whitespace-nowrap">
            Show top
          </Label>
          <Select value={String(limit)} onValueChange={(v) => setLimit(parseInt(v))}>
            <SelectTrigger id="limit" className="h-9 w-16 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="15">15</SelectItem>
              <SelectItem value="30">30</SelectItem>
              <SelectItem value="50">50</SelectItem>
              <SelectItem value="100">100</SelectItem>
            </SelectContent>
          </Select>
          <span className="whitespace-nowrap text-xs text-muted-foreground">
            {filtered.length} stocks matching
          </span>
        </div>
      </div>
      {customRanking && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span className="text-muted-foreground">
            Sorted by {headlineColumn?.label} · {sortDir === "asc" ? "ascending" : "descending"}
          </span>
          <button
            type="button"
            onClick={() => setSort(defaultSort, defaultDir)}
            className="min-h-6 text-primary-text underline-offset-4 hover:underline focus-visible:outline-ring"
          >
            Restore default ranking
          </button>
        </div>
      )}

      {/* Mobile: ranked frame rows (the dynamic multi-metric table can't fit a phone) */}
      <ol className="md:hidden border-t border-border" aria-label="Ranked stocks">
        {sorted.length === 0 ? (
          <li className="py-8 text-center text-muted-foreground">No data available.</li>
        ) : (
          sorted.map((s, index) => {
            const headlineValue = headlineColumn ? s[headlineColumn.key] : null;
            return (
              <li key={s.ticker} className="border-b border-border/60 py-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs text-muted-foreground shrink-0 w-[3ch] text-right">
                      {index + 1}
                    </span>
                    <TickerLink ticker={s.ticker} />
                  </div>
                  {headlineColumn && (
                    <span className="shrink-0 text-right">
                      <span className="block text-xs text-muted-foreground">
                        {headlineColumn.label}
                      </span>
                      {headlineColumn.render ? (
                        headlineColumn.render(s)
                      ) : headlineColumn.deltaMode && typeof headlineValue === "number" ? (
                        <Delta value={headlineValue} mode={headlineColumn.deltaMode} />
                      ) : (
                        <span
                          className={`text-sm tabular-nums ${headlineColumn.colorFn?.(headlineValue ?? NaN) ?? "text-foreground"}`}
                        >
                          {headlineColumn.format
                            ? headlineColumn.format(headlineValue ?? NaN, s)
                            : String(headlineValue ?? "—")}
                        </span>
                      )}
                    </span>
                  )}
                </div>
                <div className="mt-1 pl-[calc(3ch+0.5rem)]">
                  <CompanyLink ticker={s.ticker} company={s.company} showStar />
                </div>
                <dl className="mt-2 pl-[calc(3ch+0.5rem)] grid grid-cols-3 gap-x-2 gap-y-2">
                  {metricColumns.map((col) => {
                    const rawVal = s[col.key];
                    return (
                      <div key={col.key} className="min-w-0">
                        <dt className="metric-label truncate !text-[11px]">{col.label}</dt>
                        <dd className="text-sm">
                          {col.render ? (
                            col.render(s)
                          ) : col.deltaMode && typeof rawVal === "number" ? (
                            <Delta value={rawVal} mode={col.deltaMode} />
                          ) : (
                            <span
                              className={
                                col.colorFn ? col.colorFn(rawVal ?? NaN) : "text-foreground"
                              }
                            >
                              {col.format ? col.format(rawVal ?? NaN, s) : String(rawVal)}
                            </span>
                          )}
                        </dd>
                      </div>
                    );
                  })}
                </dl>
              </li>
            );
          })
        )}
      </ol>

      {/* Desktop: the ranked table */}
      <div className="frame hidden md:block">
        <TableFrame label="Ranked stocks">
          <table className="w-full text-sm" aria-label="Ranked stocks">
            <thead>
              <tr className="text-xs">
                <th scope="col" className="text-right px-3 py-2 w-12">
                  #
                </th>
                <th scope="col" className="text-left px-3 py-2">
                  Ticker
                </th>
                <th scope="col" className="text-left px-3 py-2">
                  Company
                </th>
                {columns.map((col) => (
                  <SortableHeader
                    key={col.key}
                    label={col.label}
                    sortKey={col.key}
                    currentKey={sortKey}
                    currentDir={sortDir}
                    onSort={toggleSort}
                    align={col.align ?? "center"}
                    tooltip={col.tooltip}
                  />
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.length === 0 ? (
                <tr>
                  <td
                    colSpan={3 + columns.length}
                    className="p-8 text-center text-muted-foreground"
                  >
                    No data available.
                  </td>
                </tr>
              ) : (
                sorted.map((s, index) => (
                  <tr key={s.ticker} className="data-table-row">
                    <td className="p-3 text-right text-muted-foreground text-xs">{index + 1}</td>
                    <td className="p-3">
                      <TickerLink ticker={s.ticker} />
                    </td>
                    <td className="p-3">
                      <CompanyLink
                        ticker={s.ticker}
                        company={s.company}
                        className="max-w-[180px] xl:max-w-[260px]"
                        showStar
                      />
                    </td>
                    {columns.map((col) => {
                      const align = col.align ?? "center";
                      const rawVal = s[col.key];
                      if (col.render) {
                        return (
                          <td key={col.key} className={`p-3 ${ALIGN_TEXT[align]}`}>
                            <div className={ALIGN_FLEX[align]}>{col.render(s)}</div>
                          </td>
                        );
                      }
                      if (col.deltaMode && typeof rawVal === "number") {
                        return (
                          <td key={col.key} className={`p-3 ${ALIGN_TEXT[align]} font-mono`}>
                            <div className={ALIGN_FLEX[align]}>
                              <Delta value={rawVal} mode={col.deltaMode} />
                            </div>
                          </td>
                        );
                      }
                      const display = col.format ? col.format(rawVal ?? NaN, s) : String(rawVal);
                      const colorClass = col.colorFn ? col.colorFn(rawVal ?? NaN) : "";
                      return (
                        <td
                          key={col.key}
                          className={`p-3 ${ALIGN_TEXT[align]} font-mono ${colorClass}`}
                        >
                          {display}
                        </td>
                      );
                    })}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </TableFrame>
      </div>
    </div>
  );
}

const netColor = (v: number) => (v > 0 ? "delta-positive" : v < 0 ? "delta-negative" : "");

const DEFAULT_TAB = "smartscore";

export default function QuarterlyTrends() {
  usePageMeta({
    title: QUARTERLY_PAGE.title,
    description: QUARTERLY_PAGE.description,
    canonical: canonicalUrl(QUARTERLY_PAGE.path),
  });

  const { quarters, latestQuarter } = useAvailableQuarters();
  const [selectedQuarter, setSelectedQuarter] = useResearchState<Quarter | undefined>(
    "quarter",
    undefined,
  );
  const quarter = selectedQuarter ?? latestQuarter;
  const [progress, setProgress] = useState({ msg: "", pct: 0 });
  const { starred: starredStocks } = useStarred("stock");
  const { starred: starredFunds } = useStarred("fund");
  const [filterStarredStocks, setFilterStarredStocks] = useResearchState("starredStocks", false);
  const [filterStarredFunds, setFilterStarredFunds] = useResearchState("starredFunds", false);
  const anyStarredFilter = filterStarredStocks || filterStarredFunds;

  // URL sync: ?tab=<id> drives the active analysis tab so the view is
  // shareable / back-forward navigable. Missing or unknown tab → default.
  const [searchParams, setSearchParams] = useSearchParams();
  const urlTab = searchParams.get("tab");
  const [activeTab, setActiveTab] = useState<string>(isStrategyTab(urlTab) ? urlTab : DEFAULT_TAB);
  const strategyTabsRef = useRef<HTMLDivElement>(null);
  // Canonical setState-in-effect: syncing state with an external system
  // (the URL). The setter short-circuits when the value already matches.
  /* oxlint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const param = searchParams.get("tab");
    const next = isStrategyTab(param) ? param : DEFAULT_TAB;
    setActiveTab((current) => (current === next ? current : next));
  }, [searchParams]);
  /* oxlint-enable react-hooks/set-state-in-effect */

  const activeFundFilter = filterStarredFunds && starredFunds.size > 0 ? starredFunds : undefined;

  const {
    data: rawData = [],
    isLoading,
    isError,
    error,
  } = useQuarterAnalysis(quarter, {
    onProgress: (msg, pct) => setProgress({ msg, pct }),
    fundFilter: activeFundFilter,
  });

  useEffect(() => {
    strategyTabsRef.current
      ?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')
      ?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [activeTab, isLoading]);

  const { data: quarterFundList = [] } = useQuery({
    queryKey: ["quarterFundList", quarter],
    queryFn: quarter ? () => getQuarterFundList(quarter) : skipToken,
    staleTime: Infinity,
  });
  // Per-tab AnalysisTable defaults sourced from the shared strategy registry
  // (src/lib/strategies.ts), so the backtest and these screens stay in sync.
  const tableDefaults = (tab: string) => {
    const def = STRATEGY_BY_TAB[tab];
    return {
      defaultSort: def.sortKey,
      defaultDir: def.ascending ? ("asc" as const) : ("desc" as const),
      defaultMinHolders: def.minHolders
        ? Math.max(1, Math.ceil(quarterFundList.length / (def.minHoldersDivisor ?? 10)))
        : 0,
      defaultFilterInfinite: def.excludeInfiniteDelta,
      deltaSign: def.deltaSign,
    };
  };

  const data = useMemo(() => {
    if (filterStarredStocks && starredStocks.size > 0) {
      return rawData.filter((s) => starredStocks.has(s.ticker));
    }
    return rawData;
  }, [rawData, filterStarredStocks, starredStocks]);
  // Keep the registry's question visible; the tab tooltip retains its full explanation.
  const questionDescription = STRATEGY_BY_TAB[activeTab].description
    .split(/[:,]/)[0]
    .replace(/^Stocks ranked by /, "Ranked by ")
    .replace(/^Stocks with the /, "")
    .replace(/^Stocks attracting /, "Attracting ");

  return (
    <div className="space-y-3 min-w-0 max-w-screen-2xl">
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="page-title">
              <BarChart3 aria-hidden="true" className="h-5 w-5 text-muted-foreground" />
              Quarterly Trends
            </h1>
            <p className="text-sm text-muted-foreground mt-1.5">
              Cross-fund consensus signals for {quarter ? quarter.replace("Q", " Q") : "…"}
              {anyStarredFilter && <span className="ml-1 text-muted-foreground">(filtered)</span>}
            </p>
          </div>
          <div className="flex w-full items-center justify-between gap-2 sm:w-auto sm:justify-start">
            {STRATEGY_BY_TAB[activeTab] && (
              <Link
                to={performanceFor(STRATEGY_BY_TAB[activeTab].id)}
                title={`See the ${STRATEGY_BY_TAB[activeTab].label} screen's backtested track record vs the S&P 500`}
                className="inline-flex h-9 items-center gap-1.5 rounded-md px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <LineChart className="h-4 w-4" aria-hidden="true" />
                <span className="hidden sm:inline">Backtested track record</span>
                <span className="sm:hidden">Backtest</span>
                <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
            )}
            <Select
              value={quarter ?? ""}
              onValueChange={(v) => {
                if (isQuarter(v)) setSelectedQuarter(v);
              }}
            >
              <SelectTrigger aria-label="Quarter" className="order-first h-9 w-36 sm:order-none">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[...quarters].reverse().map((q) => (
                  <SelectItem key={q} value={q}>
                    {q.replace("Q", " Q")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {isError ? (
        <QueryState isError error={error} title="Could not load the quarter analysis" />
      ) : isLoading ? (
        <AnalysisProgress msg={progress.msg} pct={progress.pct} className="frame p-8" />
      ) : (
        <Tabs
          value={activeTab}
          onValueChange={(value) => {
            setActiveTab(value);
            const next = new URLSearchParams(searchParams);
            if (value === DEFAULT_TAB) next.delete("tab");
            else next.set("tab", value);
            setSearchParams(next, { replace: false });
          }}
          className="w-full min-w-0"
        >
          {/* Keep all seven questions available without widening the page. */}
          <div className="w-full min-w-0 overflow-x-auto">
            <TabsList
              ref={strategyTabsRef}
              aria-label="Strategy screen"
              className="flex h-10 w-max min-w-full flex-nowrap gap-4"
            >
              {STRATEGY_DEFS_PERF_ORDER.map((d) => (
                <Tooltip key={d.tab}>
                  <TooltipTrigger asChild>
                    <TabsTrigger value={d.tab} className="h-10 shrink-0">
                      {d.label}
                    </TabsTrigger>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-[280px] text-xs font-normal">
                    {d.description}
                  </TooltipContent>
                </Tooltip>
              ))}
            </TabsList>
          </div>
          <p
            className="mt-3 truncate text-xs text-foreground first-letter:uppercase"
            title={STRATEGY_BY_TAB[activeTab].description}
          >
            {questionDescription}
          </p>

          {/* Starred filters */}
          <StarredFilterToggle
            className="mt-3"
            fundsCount={starredFunds.size}
            stocksCount={starredStocks.size}
            filterFunds={filterStarredFunds}
            filterStocks={filterStarredStocks}
            onToggleFunds={() => setFilterStarredFunds((v) => !v)}
            onToggleStocks={() => setFilterStarredStocks((v) => !v)}
          />
          <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
            Institutional signals, not forecasts.
            <InfoTooltip text="Changes are reconstructed between disclosures, not observed trades or return forecasts." />
            <Link
              to={learnItem("what-is-smart-score")}
              className="text-primary-text hover:underline underline-offset-4"
            >
              FAQ
            </Link>
          </p>

          <TabsContent value="smartscore" className="mt-3">
            <AnalysisTable
              data={data}
              {...tableDefaults("smartscore")}
              disableFilters={anyStarredFilter}
              columns={[
                {
                  key: "smartScore",
                  label: "Smart Score",
                  render: (row) =>
                    row.smartScore != null ? (
                      <SmartScoreBadge score={row.smartScore} size="sm" />
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    ),
                  tooltip:
                    "Relative institutional screen (1–10): equal-weight blend of Breadth, Momentum and Conviction. Not a return forecast.",
                },
                {
                  key: "holderCount",
                  label: "Holders",
                  tooltip: "Total number of tracked funds holding this stock.",
                },
                {
                  key: "netBuyers",
                  label: "Net Buyers",
                  colorFn: netColor,
                  tooltip: "Buyers minus sellers this quarter.",
                },
                {
                  key: "avgPortfolioPct",
                  label: "Avg Ptf %",
                  format: (v) => `${v.toFixed(2)}%`,
                  tooltip: "Average portfolio weight across holders.",
                },
                {
                  key: "delta",
                  label: "Aggregate Δ %",
                  deltaMode: "percent",
                  tooltip:
                    "Reconstructed position Δ $ / (total held value − position Δ $). Not aggregate share growth or investment return.",
                },
                {
                  key: "totalValue",
                  label: "Total Value",
                  format: (v) => formatValue(v),
                  tooltip: "Total institutional value across all tracked holders.",
                },
              ]}
            />
          </TabsContent>

          <TabsContent value="consensus" className="mt-3">
            <AnalysisTable
              data={data}
              {...tableDefaults("consensus")}
              disableFilters={anyStarredFilter}
              columns={[
                {
                  key: "delta",
                  label: "Aggregate Δ %",
                  deltaMode: "percent",
                  tooltip:
                    "Reconstructed position Δ $ / (total held value − position Δ $). Not aggregate share growth or investment return.",
                },
                {
                  key: "netBuyers",
                  label: "Net Buyers",
                  colorFn: netColor,
                  tooltip: "Buyers minus sellers this quarter.",
                },
                {
                  key: "buyerCount",
                  label: "Buyers",
                  tooltip: "Number of funds that increased their position.",
                },
                {
                  key: "sellerCount",
                  label: "Sellers",
                  tooltip: "Number of funds that decreased their position.",
                },
                {
                  key: "holderCount",
                  label: "Holders",
                  tooltip: "Total number of tracked funds holding this stock.",
                },
                {
                  key: "totalDeltaValue",
                  label: "Position Δ $",
                  deltaMode: "currency",
                  tooltip:
                    "Estimated dollar amount of position changes at reporting prices, not observed trade execution amounts.",
                },
              ]}
            />
          </TabsContent>

          <TabsContent value="new" className="mt-3">
            <AnalysisTable
              data={data}
              {...tableDefaults("new")}
              disableFilters={anyStarredFilter}
              columns={[
                {
                  key: "newHolderCount",
                  label: "New Holders",
                  tooltip: "Funds that opened a brand-new position this quarter.",
                },
                {
                  key: "netBuyers",
                  label: "Net Buyers",
                  colorFn: netColor,
                  tooltip: "Buyers minus sellers this quarter.",
                },
                {
                  key: "holderCount",
                  label: "Holders",
                  tooltip: "Total number of tracked funds holding this stock.",
                },
                {
                  key: "delta",
                  label: "Aggregate Δ %",
                  deltaMode: "percent",
                  tooltip:
                    "Reconstructed position Δ $ / (total held value − position Δ $). Not aggregate share growth or investment return.",
                },
                {
                  key: "totalDeltaValue",
                  label: "Position Δ $",
                  deltaMode: "currency",
                  tooltip:
                    "Estimated dollar amount of position changes at reporting prices, not observed trade execution amounts.",
                },
                {
                  key: "totalValue",
                  label: "Total Value",
                  format: (v) => formatValue(v),
                  tooltip: "Total institutional value across all tracked holders.",
                },
              ]}
            />
          </TabsContent>

          <TabsContent value="increasing" className="mt-3">
            <AnalysisTable
              data={data}
              {...tableDefaults("increasing")}
              disableFilters={anyStarredFilter}
              columns={[
                {
                  key: "newHolderCount",
                  label: "New Holders",
                  tooltip: "Funds that opened a brand-new position this quarter.",
                },
                {
                  key: "netBuyers",
                  label: "Net Buyers",
                  colorFn: netColor,
                  tooltip: "Buyers minus sellers this quarter.",
                },
                {
                  key: "holderCount",
                  label: "Holders",
                  tooltip: "Total number of tracked funds holding this stock.",
                },
                {
                  key: "delta",
                  label: "Aggregate Δ %",
                  deltaMode: "percent",
                  tooltip:
                    "Reconstructed position Δ $ / (total held value − position Δ $). Not aggregate share growth or investment return.",
                },
                {
                  key: "totalDeltaValue",
                  label: "Position Δ $",
                  deltaMode: "currency",
                  tooltip:
                    "Estimated dollar amount of position changes at reporting prices, not observed trade execution amounts.",
                },
                {
                  key: "totalValue",
                  label: "Total Value",
                  format: (v) => formatValue(v),
                  tooltip: "Total institutional value across all tracked holders.",
                },
              ]}
            />
          </TabsContent>

          <TabsContent value="decreasing" className="mt-3">
            <AnalysisTable
              data={data}
              {...tableDefaults("decreasing")}
              disableFilters={anyStarredFilter}
              columns={[
                {
                  key: "closeCount",
                  label: "Closers",
                  tooltip: "Funds that completely exited their position this quarter.",
                },
                {
                  key: "netBuyers",
                  label: "Net Buyers",
                  colorFn: netColor,
                  tooltip: "Buyers minus sellers this quarter.",
                },
                {
                  key: "holderCount",
                  label: "Holders",
                  tooltip: "Total number of tracked funds holding this stock.",
                },
                {
                  key: "delta",
                  label: "Aggregate Δ %",
                  deltaMode: "percent",
                  tooltip:
                    "Reconstructed position Δ $ / (total held value − position Δ $). Not aggregate share growth or investment return.",
                },
                {
                  key: "totalDeltaValue",
                  label: "Position Δ $",
                  deltaMode: "currency",
                  tooltip:
                    "Estimated dollar amount of position changes at reporting prices, not observed trade execution amounts.",
                },
                {
                  key: "totalValue",
                  label: "Total Value",
                  format: (v) => formatValue(v),
                  tooltip: "Total institutional value across all tracked holders.",
                },
              ]}
            />
          </TabsContent>

          <TabsContent value="bigbets" className="mt-3">
            <AnalysisTable
              data={data}
              {...tableDefaults("bigbets")}
              disableFilters={anyStarredFilter}
              columns={[
                {
                  key: "maxPortfolioPct",
                  label: "Max Ptf %",
                  format: (v) => `${v.toFixed(1)}%`,
                  tooltip: "Highest portfolio weight allocated by any single fund.",
                },
                {
                  key: "avgPortfolioPct",
                  label: "Avg Ptf %",
                  format: (v) => `${v.toFixed(2)}%`,
                  tooltip: "Average portfolio weight across all holding funds.",
                },
                {
                  key: "delta",
                  label: "Aggregate Δ %",
                  deltaMode: "percent",
                  tooltip:
                    "Reconstructed position Δ $ / (total held value − position Δ $). Not aggregate share growth or investment return.",
                },
                {
                  key: "totalDeltaValue",
                  label: "Position Δ $",
                  deltaMode: "currency",
                  tooltip:
                    "Estimated dollar amount of position changes at reporting prices, not observed trade execution amounts.",
                },
                {
                  key: "totalValue",
                  label: "Total Value",
                  format: (v) => formatValue(v),
                  tooltip: "Total institutional value across all tracked holders.",
                },
              ]}
            />
          </TabsContent>

          <TabsContent value="avgportfolio" className="mt-3">
            <AnalysisTable
              data={data}
              {...tableDefaults("avgportfolio")}
              disableFilters={anyStarredFilter}
              columns={[
                {
                  key: "avgPortfolioPct",
                  label: "Avg Ptf %",
                  format: (v) => `${v.toFixed(2)}%`,
                  tooltip: "Average portfolio weight across all holding funds.",
                },
                {
                  key: "maxPortfolioPct",
                  label: "Max Ptf %",
                  format: (v) => `${v.toFixed(1)}%`,
                  tooltip: "Highest portfolio weight allocated by any single fund.",
                },
                {
                  key: "holderCount",
                  label: "Holders",
                  tooltip: "Total number of tracked funds holding this stock.",
                },
                {
                  key: "delta",
                  label: "Aggregate Δ %",
                  deltaMode: "percent",
                  tooltip:
                    "Reconstructed position Δ $ / (total held value − position Δ $). Not aggregate share growth or investment return.",
                },
              ]}
            />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
