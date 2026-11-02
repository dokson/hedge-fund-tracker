import { useState, useMemo, useEffect, useRef } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { getStocks, formatValue, type Stock, type StockQuarterAnalysis } from "@/lib/dataService";
import { compareBySmartScore } from "@/lib/smartScore";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { useSortState } from "@/hooks/useSortState";
import { useResearchState } from "@/hooks/useResearchState";
import { SortArrow } from "@/components/ui/SortArrow";
import {
  ABOVE_STRETCHED_LINK,
  STRETCHED_CARD,
  STRETCHED_LINK,
} from "@/components/ui/stretchedLink";
import { useQuarterAnalysis } from "@/hooks/useQuarterAnalysis";
import { SearchInput } from "@/components/ui/SearchInput";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { QueryState } from "@/components/ui/QueryState";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { LayoutGrid, SortAsc, X, DollarSign, Gauge, Star } from "lucide-react";
import SectorHeatmap from "@/components/SectorHeatmap";
import YFinanceClassificationTreeVisual from "@/components/YFinanceClassificationTreeVisual";
import { HoldingsTreemap } from "@/components/HoldingsTreemap";
import { useStarred } from "@/hooks/useStarred";
import { StarButton } from "@/components/StarButton";
import { SmartScoreBadge } from "@/components/SmartScoreBadge";
import { TickerLink } from "@/components/EntityLinks";
import { CompanyLogo } from "@/components/CompanyLogo";
import { matchesQuery } from "@/lib/utils";
import { learnItem, stockPath } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";
import { usePageMeta } from "@/hooks/usePageMeta";
import { STOCKS_PAGE } from "@/lib/pageMeta";
import { VirtualList } from "@/components/ui/VirtualList";

const ALPHABET = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
const VALID_TABS = ["score", "starred", "byvalue", "sectors", "alphabetical"] as const;
type BrowserTab = (typeof VALID_TABS)[number];

function isValidTab(value: string | null): value is BrowserTab {
  return VALID_TABS.some((tab) => tab === value);
}

// Column template for the windowed "Score" grid (kept literal for Tailwind).
const SCORE_GRID_COLS =
  "grid grid-cols-[3rem_7.5rem_minmax(0,1fr)_7.5rem_minmax(4.5rem,7rem)_minmax(4.5rem,7rem)_minmax(4.5rem,7rem)]";

// Same rationale as SCORE_GRID_COLS.
const VALUE_GRID_COLS =
  "grid grid-cols-[3rem_7.5rem_minmax(0,1fr)_minmax(6.5rem,auto)_minmax(6rem,auto)_4rem_6.5rem_8rem]";

// The div-based header of a windowed grid, styled like `thead th`.
const GRID_HEADER_CLASS = "items-center border-b border-border text-xs text-muted-foreground";

/** Neutral placeholders preserve the measured list geometry until analysis is ready. */
function AnalysisRowsSkeleton({
  kind,
  desktop = false,
}: {
  kind: "score" | "value";
  desktop?: boolean;
}) {
  return (
    <div
      aria-hidden="true"
      className={`h-[70vh] overflow-hidden ${desktop ? "hidden md:block" : "md:hidden pr-1"}`}
    >
      {Array.from({ length: 16 }, (_, row) =>
        desktop ? (
          <div
            key={row}
            className={`${kind === "score" ? SCORE_GRID_COLS : VALUE_GRID_COLS} h-[62px] items-center border-b border-border`}
          >
            {Array.from({ length: kind === "score" ? 7 : 8 }, (_, column) => (
              <div key={column} className="min-w-0 px-3">
                <Skeleton className={column === 2 ? "h-3 w-3/4" : "h-3 w-full"} />
              </div>
            ))}
          </div>
        ) : (
          <div key={row} className={kind === "score" ? "h-[149px] pb-3" : "h-[117px] pb-3"}>
            <div className="h-full border-b border-border py-2">
              <div className="flex h-8 items-center gap-2">
                <Skeleton className="h-3 w-4" />
                <Skeleton className="h-8 w-8 shrink-0" />
                <Skeleton className="h-3 w-14" />
                <Skeleton className="ml-auto h-5 w-10" />
              </div>
              <Skeleton className="mt-1 h-5 w-2/3" />
              <div className="mt-2 space-y-1">
                {Array.from({ length: kind === "score" ? 3 : 1 }, (_, component) => (
                  <Skeleton key={component} className="h-4 w-full" />
                ))}
              </div>
            </div>
          </div>
        ),
      )}
    </div>
  );
}

/** Rank cell. Podium ranks are the same muted number, one weight heavier. */
function RankBadge({ rank }: { rank: number }) {
  return (
    <span
      className={`text-xs tabular-nums text-muted-foreground${rank <= 3 ? " font-semibold" : ""}`}
    >
      {rank}
    </span>
  );
}

/**
 * Inline 0-100 percentile meter for a Smart Score sub-component (Breadth,
 * Momentum, Conviction): a filled track next to the number, so each row reads
 * as "score built from these parts". One colour: the number carries the value.
 */
function PercentileBar({ label, value }: { label?: string; value: number | null }) {
  return (
    <div className="flex items-center gap-1.5 min-w-0">
      {label && <span className="metric-label w-20 shrink-0">{label}</span>}
      <div className="h-1 flex-1 min-w-[2rem] rounded-sm bg-muted overflow-hidden">
        {value !== null && <div className="h-full bg-primary" style={{ width: `${value}%` }} />}
      </div>
      <span className="text-xs text-muted-foreground tabular-nums w-6 text-right shrink-0">
        {value === null ? "—" : Math.round(value)}
      </span>
    </div>
  );
}

/** Mobile row for one "By Value" entry: the seven-column table can't fit a phone. */
function ValueStockCard({
  stock,
  rank,
  maxValue,
  starred,
  smartScore,
  onToggleStar,
}: {
  stock: StockQuarterAnalysis;
  rank: number;
  maxValue: number;
  starred: boolean;
  smartScore: number | undefined;
  onToggleStar: () => void;
}) {
  const barPct = (stock.totalValue / maxValue) * 100;
  const isPositiveDelta = stock.totalDeltaValue >= 0;
  return (
    <div className={`${STRETCHED_CARD} border-b border-border py-2 hover:bg-muted/60`}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs tabular-nums text-muted-foreground shrink-0">#{rank}</span>
          <TickerLink ticker={stock.ticker} className={STRETCHED_LINK} title={stock.company} />
          {smartScore !== undefined && <SmartScoreBadge score={smartScore} size="sm" />}
        </div>
        <StarButton
          active={starred}
          onClick={onToggleStar}
          size={24}
          className={ABOVE_STRETCHED_LINK}
        />
      </div>
      <div className="company-link cursor-default mt-1 text-sm">{stock.company}</div>
      <div className="status-line mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
        <span>
          <span className="k">Value:</span> {formatValue(stock.totalValue)}
        </span>
        <span aria-hidden="true">·</span>
        <span className={isPositiveDelta ? "delta-positive" : "delta-negative"}>
          <span className="k">Position Δ $:</span> {isPositiveDelta ? "+" : "−"}
          {formatValue(Math.abs(stock.totalDeltaValue))}
        </span>
        <span aria-hidden="true">·</span>
        <span>
          <span className="k">Funds:</span> {stock.holderCount}
        </span>
      </div>
      <div className="mt-2 h-1 rounded-sm bg-muted overflow-hidden" aria-hidden="true">
        <div className="h-full bg-primary" style={{ width: `${barPct}%` }} />
      </div>
    </div>
  );
}

export default function StockBrowser() {
  usePageMeta({
    title: STOCKS_PAGE.title,
    description: STOCKS_PAGE.description,
    canonical: canonicalUrl(STOCKS_PAGE.path),
  });

  const navigate = useNavigate();
  const [search, setSearch] = useResearchState("alphabetical:search", "");
  const [activeLetter, setActiveLetter] = useResearchState<string | null>(
    "alphabetical:letter",
    null,
  );
  const ALPHA_CHUNK = 500;
  // How many top-by-value tickers are revealed in the Alphabetical tab. Bumped
  // in 500-chunk increments via the "Show 500 more" affordance. Resets to one
  // chunk whenever a search or letter filter is applied so the chunking is
  // about scale, not about the active query.
  const [alphaReveal, setAlphaReveal] = useResearchState("alphabetical:reveal", ALPHA_CHUNK);
  const [valueSearch, setValueSearch] = useResearchState("value:search", "");
  const [scoreSearch, setScoreSearch] = useResearchState("score:search", "");
  const {
    sortKey: valueSortKey,
    sortDir: valueSortDir,
    toggleSort: toggleValueSort,
    setSort: setValueSort,
  } = useSortState<"totalValue" | "totalDeltaValue" | "holderCount" | "smartScore">(
    "totalValue",
    "desc",
    "value",
  );
  const [cachedIndustryFilter, setIndustryFilter] = useResearchState<string | null>(
    "value:industry",
    null,
  );
  const [sectorFilter, setSectorFilter] = useResearchState<string | null>("value:sector", null);
  const [activeTab, setActiveTab] = useResearchState<string | null>("tab", null);
  const { starred, toggle: toggleStar, isStarred } = useStarred("stock");
  const [searchParams, setSearchParams] = useSearchParams();
  // Explicit URL controls take precedence over this session's retained view.
  const industryParam = searchParams.get("industry");
  const industryFilter = industryParam || cachedIndustryFilter;
  const defaultTab = starred.size > 0 ? "starred" : "score";
  const urlTab = searchParams.get("tab");
  const selectedTab = industryParam
    ? "byvalue"
    : isValidTab(urlTab)
      ? urlTab
      : (activeTab ?? defaultTab);
  // Tabs are mounted lazily — children render only after the tab is visited at
  // least once. Once visited, they stay in the tree so switching tabs is instant.
  const [visitedTabs, setVisitedTabs] = useState<Set<string>>(() => new Set([selectedTab]));
  const tabListRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    tabListRef.current
      ?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')
      ?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [selectedTab, starred.size]);

  // Syncs local state from the URL; guarded to avoid cascading renders.
  /* oxlint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (industryParam) {
      setIndustryFilter(industryParam);
      setSectorFilter(null);
      setActiveTab("byvalue");
      // Retain the filter before replacing its one-shot deep-link parameter.
      const next = new URLSearchParams(searchParams);
      next.delete("industry");
      next.set("tab", "byvalue");
      setSearchParams(next, { replace: true });
    }
  }, [
    industryParam,
    searchParams,
    setSearchParams,
    setIndustryFilter,
    setSectorFilter,
    setActiveTab,
  ]);

  useEffect(() => {
    if (!industryParam && isValidTab(urlTab)) setActiveTab(urlTab);
    if (!industryParam && !isValidTab(urlTab)) {
      // Every history entry names its tab, so Back/forward always lands on the right one.
      const next = new URLSearchParams(searchParams);
      next.set("tab", selectedTab);
      setSearchParams(next, { replace: true });
    }
    setVisitedTabs((prev) => (prev.has(selectedTab) ? prev : new Set(prev).add(selectedTab)));
  }, [industryParam, urlTab, selectedTab, setActiveTab, searchParams, setSearchParams]);
  /* oxlint-enable react-hooks/set-state-in-effect */

  // Progressive reveal: render the first chunk on mount, hydrate the rest after
  // the browser is idle so the initial INP isn't blocked by 500 cards of React
  // tree + <img> elements. Reset whenever the filtered list churns.
  const ALPHA_INITIAL_RENDER = 80;
  const [renderCount, setRenderCount] = useState(ALPHA_INITIAL_RENDER);

  const {
    data: stocks = [],
    isLoading,
    isError: stocksIsError,
    error: stocksError,
  } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
  });

  const { latestQuarter, isLoading: quartersLoading } = useAvailableQuarters();
  const {
    data: quarterData = [],
    isSuccess: quarterReady,
    isError: quarterIsError,
    error: quarterError,
  } = useQuarterAnalysis(latestQuarter);
  // A disabled query is not "loading" while the latest quarter is still unknown.
  // Only a successful analysis may establish scores, including legitimate floor rows.
  const analysisReady = Boolean(latestQuarter) && quarterReady;
  const analysisLoading =
    quartersLoading || (Boolean(latestQuarter) && !quarterReady && !quarterIsError);
  const scoreLoading = analysisLoading || isLoading;

  const uniqueStocks = useMemo(() => {
    const seen = new Set<string>();
    return stocks.filter((s) => {
      if (seen.has(s.ticker)) return false;
      seen.add(s.ticker);
      return true;
    });
  }, [stocks]);

  const topTickersByValue = useMemo(() => {
    if (quarterData.length === 0) return null;
    const sorted = [...quarterData].sort((a, b) => b.totalValue - a.totalValue);
    return new Set(sorted.slice(0, alphaReveal).map((s) => s.ticker));
  }, [quarterData, alphaReveal]);

  const starredStocks = useMemo(() => {
    return uniqueStocks
      .filter((s) => starred.has(s.ticker))
      .sort((a, b) => a.ticker.localeCompare(b.ticker));
  }, [uniqueStocks, starred]);

  const filtered = useMemo(() => {
    let list = uniqueStocks;
    if (topTickersByValue && !search) {
      list = list.filter((s) => topTickersByValue.has(s.ticker));
    }
    if (activeLetter) {
      if (activeLetter === "#") {
        list = list.filter((s) => !/^[A-Z]/i.test(s.ticker));
      } else {
        list = list.filter((s) => s.ticker.toUpperCase().startsWith(activeLetter));
      }
    }
    if (search) {
      list = list.filter((s) => matchesQuery(search, s.ticker, s.company));
    }
    return list.sort((a, b) => a.ticker.localeCompare(b.ticker));
  }, [uniqueStocks, search, activeLetter, topTickersByValue]);

  const grouped = useMemo(() => {
    const visible = filtered.slice(0, renderCount);
    const groups = new Map<string, Stock[]>();
    for (const s of visible) {
      const letter = /^[A-Z]/i.test(s.ticker) ? s.ticker[0].toUpperCase() : "#";
      const arr = groups.get(letter) || [];
      arr.push(s);
      groups.set(letter, arr);
    }
    return groups;
  }, [filtered, renderCount]);

  // Hydrate the remaining cards once the browser is idle, falling back to a
  // macrotask where requestIdleCallback is unavailable. Each branch returns
  // its own paired cleanup so schedule/cancel can't drift apart.
  useEffect(() => {
    if (renderCount >= filtered.length) return;
    const hydrate = () => setRenderCount(filtered.length);
    if (typeof window.requestIdleCallback === "function") {
      const handle = window.requestIdleCallback(hydrate);
      return () => window.cancelIdleCallback(handle);
    }
    const handle = window.setTimeout(hydrate, 0);
    return () => window.clearTimeout(handle);
  }, [filtered.length, renderCount]);

  // Reset both chunk caps when the filter set changes (search/letter/reveal).
  // Render-time state adjustment pattern (React docs: "storing information
  // from previous renders") avoids the set-state-in-effect anti-pattern that
  // would cause an extra render + flicker on every filter tick.
  const filterKey = `${search}|${activeLetter ?? ""}|${alphaReveal}`;
  const [lastFilterKey, setLastFilterKey] = useState(filterKey);
  if (lastFilterKey !== filterKey) {
    setLastFilterKey(filterKey);
    setRenderCount(ALPHA_INITIAL_RENDER);
    if (search || activeLetter) setAlphaReveal(ALPHA_CHUNK);
  }

  // Ticker → industry/sector lookup, derived from stocks.csv (joined with
  // sector_hierarchy inside getStocks). Used to filter the By Value table when
  // the user clicks an industry (Yahoo classification tree) or a sector (the
  // "Institutional Value by Sector" heatmap) in the Sectors tab.
  const tickerIndustry = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of stocks) {
      if (s.industry && !map.has(s.ticker)) map.set(s.ticker, s.industry);
    }
    return map;
  }, [stocks]);

  const tickerSector = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of stocks) {
      if (s.sector && !map.has(s.ticker)) map.set(s.ticker, s.sector);
    }
    return map;
  }, [stocks]);

  const valueRanked = useMemo(() => {
    let list = [...quarterData];
    if (industryFilter) {
      list = list.filter((s) => tickerIndustry.get(s.ticker) === industryFilter);
    } else if (sectorFilter) {
      list = list.filter((s) => tickerSector.get(s.ticker) === sectorFilter);
    }
    list.sort((a, b) => {
      if (valueSortKey === "smartScore") {
        const byScore = compareBySmartScore(a, b);
        return valueSortDir === "desc" ? byScore : -byScore;
      }
      const va = a[valueSortKey] ?? -1;
      const vb = b[valueSortKey] ?? -1;
      return valueSortDir === "desc" ? vb - va : va - vb;
    });
    if (valueSearch) {
      list = list.filter((s) => matchesQuery(valueSearch, s.ticker, s.company));
    }
    return list;
  }, [
    quarterData,
    valueSearch,
    valueSortKey,
    valueSortDir,
    industryFilter,
    tickerIndustry,
    sectorFilter,
    tickerSector,
  ]);

  // Ranked smart-score list: scored rows straight from the quarter analysis
  // (computed on the fly like every other consensus metric) plus 1.0-floor
  // rows for the rest of the registry, so every ticker is searchable.
  const scoreRanked = useMemo(() => {
    if (!analysisReady) return [];
    const held = new Set(quarterData.map((s) => s.ticker));
    const floor: StockQuarterAnalysis[] = uniqueStocks
      .filter((s) => !held.has(s.ticker))
      .map((s) => ({
        ticker: s.ticker,
        company: s.company,
        totalValue: 0,
        totalDeltaValue: 0,
        maxPortfolioPct: 0,
        avgPortfolioPct: 0,
        buyerCount: 0,
        sellerCount: 0,
        holderCount: 0,
        newHolderCount: 0,
        closeCount: 0,
        highConvictionCount: 0,
        netBuyers: 0,
        buyerSellerRatio: 0,
        ownershipDeltaAvg: 0,
        fundConcentrationAvg: 0,
        delta: 0,
        smartScore: 1.0,
        scoreBreadth: 0,
        scoreMomentum: 0,
        scoreConviction: 0,
      }));
    let list = [...quarterData, ...floor];
    list.sort((a, b) => compareBySmartScore(a, b) || a.ticker.localeCompare(b.ticker));
    if (scoreSearch) {
      list = list.filter((s) => matchesQuery(scoreSearch, s.ticker, s.company));
    }
    return list;
  }, [analysisReady, quarterData, uniqueStocks, scoreSearch]);

  const heatmapData = useMemo(() => {
    if (quarterData.length === 0) return [];
    const sorted = [...quarterData].sort((a, b) => b.totalValue - a.totalValue);
    return sorted.slice(0, 20).map((s) => ({
      name: s.ticker,
      company: s.company,
      value: s.totalValue,
      deltaPct: s.delta === Infinity ? 100 : s.delta,
      delta:
        s.delta === Infinity
          ? "NEW"
          : s.delta > 0
            ? "INCREASE"
            : s.delta < 0
              ? "DECREASE"
              : "NO CHANGE",
    }));
  }, [quarterData]);

  const maxValue = useMemo(() => {
    if (quarterData.length === 0) return 1;
    return Math.max(...quarterData.map((s) => s.totalValue)) || 1;
  }, [quarterData]);

  // Mount the requested tab and keep explicit tab navigation in the URL.
  function switchToTab(value: string) {
    setActiveTab(value);
    setVisitedTabs((prev) => (prev.has(value) ? prev : new Set(prev).add(value)));
    const next = new URLSearchParams(searchParams);
    next.set("tab", value);
    setSearchParams(next, { replace: false });
  }

  return (
    <div className="w-full min-w-0 space-y-6 max-w-screen-2xl">
      <div>
        <h1 className="page-title">Stocks</h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Browse {uniqueStocks.length.toLocaleString()} tracked securities
        </p>
      </div>

      <Tabs value={selectedTab} onValueChange={switchToTab} className="min-w-0 space-y-4">
        <div className="w-full min-w-0 overflow-x-auto">
          <TabsList
            ref={tabListRef}
            aria-label="Stock views"
            className="flex w-max min-w-full gap-3"
          >
            <TabsTrigger value="score" className="shrink-0 gap-1.5">
              <Gauge className="h-3.5 w-3.5" /> Smart Score
            </TabsTrigger>
            {starred.size > 0 && (
              <TabsTrigger value="starred" className="shrink-0 gap-1.5 group">
                <Star className="h-3.5 w-3.5" fill="currentColor" /> Starred
                <span className="ml-1 text-xs tabular-nums leading-none">({starred.size})</span>
              </TabsTrigger>
            )}
            <TabsTrigger value="byvalue" className="shrink-0 gap-1.5">
              <DollarSign className="h-3.5 w-3.5" /> Value
            </TabsTrigger>
            <TabsTrigger value="sectors" className="shrink-0 gap-1.5">
              <LayoutGrid className="h-3.5 w-3.5" /> Sectors
            </TabsTrigger>
            <TabsTrigger value="alphabetical" className="shrink-0 gap-1.5">
              <SortAsc className="h-3.5 w-3.5" /> Alphabetical
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="starred" className="space-y-4">
          {starredStocks.length === 0 ? (
            <EmptyState
              icon={Star}
              title="No starred stocks yet."
              description="Click the ★ icon on any stock to add it here."
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-px bg-border border border-border">
              {starredStocks.map((stock) => (
                <div
                  key={stock.ticker}
                  className={`${STRETCHED_CARD} bg-card py-2.5 px-3 hover:bg-muted/60`}
                >
                  <div className="flex items-center gap-3">
                    <CompanyLogo ticker={stock.ticker} size={28} />
                    <div className="flex flex-col min-w-0 leading-tight flex-1">
                      <Link
                        to={stockPath(stock.ticker)}
                        className={`text-sm font-medium text-foreground ${STRETCHED_LINK}`}
                        title={stock.company}
                      >
                        {stock.ticker}
                      </Link>
                      <span className="company-link text-xs cursor-default">{stock.company}</span>
                    </div>
                    <StarButton
                      active={true}
                      onClick={() => toggleStar(stock.ticker)}
                      size={24}
                      className={ABOVE_STRETCHED_LINK}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="alphabetical" className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
            <SearchInput
              label="Search ticker or company"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              wrapperClassName="w-full sm:w-72"
            />
            {!search && !activeLetter && topTickersByValue && uniqueStocks.length > alphaReveal && (
              <div className="text-xs text-muted-foreground flex items-center gap-3 flex-wrap">
                <span>
                  Showing top {alphaReveal.toLocaleString()} of{" "}
                  {uniqueStocks.length.toLocaleString()} by value
                </span>
                <button
                  type="button"
                  className="inline-flex h-7 items-center rounded-md px-2 text-xs font-medium text-muted-foreground transition-colors duration-[120ms] hover:bg-muted hover:text-foreground"
                  onClick={() =>
                    setAlphaReveal((n) => Math.min(n + ALPHA_CHUNK, uniqueStocks.length))
                  }
                >
                  Show {ALPHA_CHUNK.toLocaleString()} more
                </button>
                <button
                  type="button"
                  className="inline-flex h-7 items-center rounded-md px-2 text-xs font-medium text-muted-foreground transition-colors duration-[120ms] hover:bg-muted hover:text-foreground"
                  onClick={() => setAlphaReveal(uniqueStocks.length)}
                >
                  Show all
                </button>
              </div>
            )}
          </div>

          <div
            className="grid grid-cols-7 gap-1 md:grid-flow-col md:auto-cols-fr md:grid-cols-none"
            role="group"
            aria-label="Filter by first letter"
          >
            <button
              type="button"
              onClick={() => setActiveLetter(null)}
              aria-pressed={activeLetter === null}
              className={`h-10 w-full rounded-sm text-xs font-medium transition-colors md:h-8 ${
                activeLetter === null
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              All
            </button>
            {ALPHABET.map((letter) => (
              <button
                key={letter}
                type="button"
                onClick={() => setActiveLetter(activeLetter === letter ? null : letter)}
                aria-pressed={activeLetter === letter}
                className={`h-10 w-full rounded-sm text-xs font-medium transition-colors md:h-8 ${
                  activeLetter === letter
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                {letter}
              </button>
            ))}
          </div>

          {stocksIsError ? (
            <QueryState isError error={stocksError} title="Could not load stocks" />
          ) : isLoading ? (
            <LoadingState message="Loading stocks…" />
          ) : filtered.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No stocks match your search.</p>
          ) : (
            <div className="space-y-6">
              {[...grouped.entries()].map(([letter, items]) => (
                <div key={letter}>
                  <h2 className="section-title mb-2 sticky top-0 bg-background py-1 border-b border-border">
                    {letter}
                    <span className="ml-2 text-muted-foreground">({items.length})</span>
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-px bg-border border border-border">
                    {items.map((stock) => (
                      <div
                        key={`${stock.cusip}-${stock.ticker}`}
                        // content-visibility:auto lets the browser skip layout
                        // and paint for off-screen cards; intrinsic-size keeps
                        // the scroll height stable.
                        style={{
                          contentVisibility: "auto",
                          containIntrinsicSize: "auto 56px",
                        }}
                        className={`${STRETCHED_CARD} bg-card py-2.5 px-3 hover:bg-muted/60`}
                      >
                        <div className="flex items-center gap-3">
                          <CompanyLogo ticker={stock.ticker} size={28} />
                          <div className="flex flex-col min-w-0 leading-tight flex-1">
                            <Link
                              to={stockPath(stock.ticker)}
                              className={`text-sm font-medium text-foreground ${STRETCHED_LINK}`}
                              title={stock.company}
                            >
                              {stock.ticker}
                            </Link>
                            <span className="company-link text-xs cursor-default">
                              {stock.company}
                            </span>
                          </div>
                          <StarButton
                            active={isStarred(stock.ticker)}
                            onClick={() => toggleStar(stock.ticker)}
                            size={24}
                            className={ABOVE_STRETCHED_LINK}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* ── By Value tab ── (deferred to keep initial paint snappy) */}
        {/* ── Score tab ── ranked institutional smart scores (children deferred until visited) */}
        <TabsContent value="score" className="space-y-4">
          {quarterIsError ? (
            <QueryState isError error={quarterError} title="Could not load quarter data" />
          ) : (
            (visitedTabs.has("score") || selectedTab === "score") && (
              <>
                <div className="flex flex-col sm:flex-row gap-4 items-start justify-between">
                  <SearchInput
                    label="Search ticker or company"
                    value={scoreSearch}
                    onChange={(e) => setScoreSearch(e.target.value)}
                    wrapperClassName="w-full sm:w-72"
                  />
                  <p className="text-xs text-muted-foreground">
                    {scoreLoading
                      ? "Loading stocks"
                      : `${scoreRanked.length.toLocaleString()} stocks`}{" "}
                    · {latestQuarter?.replace("Q", " Q") ?? ""} ·{" "}
                    <Link
                      to={learnItem("what-is-smart-score")}
                      className="inline-flex min-h-6 items-center text-primary-text hover:underline"
                    >
                      How is the score calculated?
                    </Link>
                  </p>
                </div>
                <p className="text-xs text-muted-foreground">
                  A relative institutional screen, not a return forecast. Ties at one decimal are
                  ordered by the unrounded score; stocks outside the analysis universe sit at 1.0.
                </p>

                {scoreLoading && (
                  <span role="status" className="sr-only">
                    Loading Smart Score…
                  </span>
                )}
                {scoreLoading ? (
                  <AnalysisRowsSkeleton kind="score" />
                ) : !analysisReady ? (
                  <p className="text-center text-muted-foreground py-8">
                    No quarter data available.
                  </p>
                ) : (
                  <VirtualList
                    scrollKey="score-mobile"
                    className="md:hidden max-h-[70vh] pr-1"
                    items={scoreRanked}
                    estimateSize={92}
                    getKey={(s) => s.ticker}
                    renderItem={(s, i) => (
                      <div className="pb-3">
                        <div
                          className={`${STRETCHED_CARD} border-b border-border py-2 hover:bg-muted/60`}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex items-center gap-2 min-w-0">
                              <RankBadge rank={i + 1} />
                              <TickerLink
                                ticker={s.ticker}
                                className={STRETCHED_LINK}
                                title={s.company}
                              />
                            </div>
                            <span className={ABOVE_STRETCHED_LINK}>
                              <SmartScoreBadge score={s.smartScore ?? 1} size="sm" />
                            </span>
                          </div>
                          <div className="company-link cursor-default mt-1 text-sm">
                            {s.company}
                          </div>
                          <div className="mt-2 space-y-1">
                            <PercentileBar label="Breadth" value={s.scoreBreadth ?? null} />
                            <PercentileBar label="Momentum" value={s.scoreMomentum ?? null} />
                            <PercentileBar label="Conviction" value={s.scoreConviction ?? null} />
                          </div>
                        </div>
                      </div>
                    )}
                  />
                )}

                <div
                  className="surface hidden md:block"
                  role="region"
                  aria-label="Stocks ranked by Smart Score"
                >
                  <div className={`${SCORE_GRID_COLS} ${GRID_HEADER_CLASS}`}>
                    <span className="text-left p-3">#</span>
                    <span className="text-left p-3">Ticker</span>
                    <span className="text-left p-3">Company</span>
                    <span className="text-right p-3 pr-4">
                      <span className="inline-flex items-center justify-end gap-1 whitespace-nowrap">
                        Smart Score
                        <InfoTooltip text="Equal-weight blend of Breadth, Momentum and Conviction, rescaled to 1–10. Latest-quarter source data may include saved non-quarterly disclosures; coverage depends on the analysis source. Not a forecast." />
                      </span>
                    </span>
                    <span className="text-left p-3 pl-4">
                      <span className="inline-flex items-center gap-1">
                        Breadth
                        <InfoTooltip text="Percentile rank of how many tracked funds hold the stock (Holder Count) — 0 to 100." />
                      </span>
                    </span>
                    <span className="text-left p-3 pl-4">
                      <span className="inline-flex items-center gap-1">
                        Momentum
                        <InfoTooltip text="Percentile rank of net fund buyers (increasing funds minus reducing funds) — 0 to 100. This is fund activity, not price momentum." />
                      </span>
                    </span>
                    <span className="text-left p-3 pl-4">
                      <span className="inline-flex items-center gap-1">
                        Conviction
                        <InfoTooltip text="Percentile rank of average portfolio allocation across holders (Avg Portfolio %), plus a capped bonus per high-conviction new entry — 0 to 100." />
                      </span>
                    </span>
                  </div>
                  {scoreLoading ? (
                    <AnalysisRowsSkeleton kind="score" desktop />
                  ) : (
                    analysisReady && (
                      <VirtualList
                        scrollKey="score-desktop"
                        className="max-h-[70vh]"
                        items={scoreRanked}
                        estimateSize={45}
                        getKey={(s) => s.ticker}
                        renderItem={(s, i) => (
                          <div
                            className={`${STRETCHED_CARD} data-table-row text-sm ${SCORE_GRID_COLS} items-center`}
                          >
                            <span className="p-3 flex items-center">
                              <RankBadge rank={i + 1} />
                            </span>
                            <span className="p-3">
                              <TickerLink
                                ticker={s.ticker}
                                className={STRETCHED_LINK}
                                title={s.company}
                              />
                            </span>
                            <span className="p-3 inline-flex items-center gap-2 min-w-0">
                              <StarButton
                                active={isStarred(s.ticker)}
                                onClick={() => toggleStar(s.ticker)}
                                size={24}
                                className={ABOVE_STRETCHED_LINK}
                              />
                              <span className="company-link cursor-default truncate">
                                {s.company}
                              </span>
                            </span>
                            <span className="p-3 text-right">
                              <span className={ABOVE_STRETCHED_LINK}>
                                <SmartScoreBadge score={s.smartScore ?? 1} size="sm" />
                              </span>
                            </span>
                            <span className="p-3">
                              <PercentileBar value={s.scoreBreadth ?? null} />
                            </span>
                            <span className="p-3">
                              <PercentileBar value={s.scoreMomentum ?? null} />
                            </span>
                            <span className="p-3">
                              <PercentileBar value={s.scoreConviction ?? null} />
                            </span>
                          </div>
                        )}
                      />
                    )
                  )}
                </div>
              </>
            )
          )}
        </TabsContent>

        <TabsContent value="byvalue" className="space-y-4">
          {!visitedTabs.has("byvalue") && selectedTab !== "byvalue" ? null : (
            <>
              {(industryFilter || sectorFilter) && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-muted-foreground">
                    Filtered by {industryFilter ? "industry" : "sector"}:
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setIndustryFilter(null);
                      setSectorFilter(null);
                    }}
                    className="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-xs font-medium text-muted-foreground transition-colors duration-[120ms] hover:bg-muted hover:text-foreground"
                    aria-label={`Clear filter ${industryFilter ?? sectorFilter}`}
                  >
                    {industryFilter ?? sectorFilter}
                    <X className="h-3 w-3" aria-hidden="true" />
                  </button>
                  {!analysisLoading && (
                    <span className="text-xs text-muted-foreground">
                      · {valueRanked.length} stock{valueRanked.length === 1 ? "" : "s"}
                    </span>
                  )}
                </div>
              )}
              {analysisReady && heatmapData.length > 0 && !industryFilter && !sectorFilter && (
                <div className="frame">
                  <h2 className="frame-title">Top 20 by Institutional Value</h2>
                  <div className="p-3">
                    <HoldingsTreemap
                      data={heatmapData}
                      onClickTicker={(t) => navigate(stockPath(t))}
                      height={300}
                    />
                  </div>
                </div>
              )}
              <div className="flex flex-col sm:flex-row gap-4 items-start justify-between">
                <SearchInput
                  label="Search ticker or company"
                  value={valueSearch}
                  onChange={(e) => setValueSearch(e.target.value)}
                  wrapperClassName="w-full sm:w-72"
                />
                <p className="text-xs text-muted-foreground">
                  {analysisLoading
                    ? "Loading stocks"
                    : `${valueRanked.length.toLocaleString()} stocks`}{" "}
                  · {latestQuarter?.replace("Q", " Q") ?? ""} · Reported institutional holdings
                  value
                </p>
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                Position changes at reporting prices, not trading cash or investment returns.{" "}
                <Link
                  to={learnItem("what-is-smart-score")}
                  className="inline-flex min-h-6 items-center text-primary-text hover:underline"
                >
                  Score methodology
                </Link>
              </p>

              {quarterIsError ? (
                <QueryState isError error={quarterError} title="Could not load quarter data" />
              ) : analysisLoading ? (
                <>
                  <span role="status" className="sr-only">
                    Loading institutional values…
                  </span>
                  <AnalysisRowsSkeleton kind="value" />
                  <div className="surface hidden md:block">
                    <div
                      aria-hidden="true"
                      className={`${VALUE_GRID_COLS} ${GRID_HEADER_CLASS} h-[57px]`}
                    >
                      {[
                        "#",
                        "Ticker",
                        "Company",
                        "Total Value",
                        "Position Δ $",
                        "Funds",
                        "Smart Score",
                        "Relative Size",
                      ].map((label) => (
                        <span key={label} className="p-3">
                          {label}
                        </span>
                      ))}
                    </div>
                    <AnalysisRowsSkeleton kind="value" desktop />
                  </div>
                </>
              ) : !analysisReady || valueRanked.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">No data available.</p>
              ) : (
                <>
                  {/* Mobile: windowed card list */}
                  <VirtualList
                    scrollKey="value-mobile"
                    className="md:hidden max-h-[70vh] pr-1"
                    items={valueRanked}
                    estimateSize={92}
                    getKey={(stock) => stock.ticker}
                    renderItem={(stock, i) => (
                      <div className="pb-3">
                        <ValueStockCard
                          stock={stock}
                          rank={i + 1}
                          smartScore={stock.smartScore}
                          maxValue={maxValue}
                          starred={isStarred(stock.ticker)}
                          onToggleStar={() => toggleStar(stock.ticker)}
                        />
                      </div>
                    )}
                  />

                  {/* Header stays outside the scroll area. */}
                  <div
                    className="surface hidden md:block"
                    role="region"
                    aria-label="Stocks ranked by institutional value"
                  >
                    <div className={`${VALUE_GRID_COLS} ${GRID_HEADER_CLASS}`}>
                      <span className="text-left p-3">#</span>
                      <span className="text-left p-3">Ticker</span>
                      <span className="text-left p-3">Company</span>
                      {(
                        [
                          ["totalValue", "Total Value", undefined],
                          ["totalDeltaValue", "Position Δ $", undefined],
                          ["holderCount", "Funds", undefined],
                          [
                            "smartScore",
                            "Smart Score",
                            "Relative institutional screen (1–10), not a return forecast. One-decimal ties are ordered by the unrounded component mean.",
                          ],
                        ] as const
                      ).map(([key, label, title]) => (
                        <span
                          key={key}

                          className="text-right p-0"
                        >
                          <button
                            type="button"
                            className="w-full p-3 text-right whitespace-nowrap hover:text-foreground hover:bg-muted/60"
                            onClick={() => toggleValueSort(key)}
                            title={title}
                          >
                            {label}
                            <SortArrow active={valueSortKey === key} direction={valueSortDir} />
                          </button>
                        </span>
                      ))}
                      <span className="p-3">Relative Size</span>
                    </div>
                    <VirtualList
                      scrollKey="value-desktop"
                      className="max-h-[70vh]"
                      items={valueRanked}
                      estimateSize={45}
                      getKey={(stock) => stock.ticker}
                      renderItem={(stock, i) => {
                        const barPct = (stock.totalValue / maxValue) * 100;
                        const isPositiveDelta = stock.totalDeltaValue >= 0;
                        return (
                          <div
                            className={`${STRETCHED_CARD} data-table-row text-sm ${VALUE_GRID_COLS} items-center`}
                          >
                            <span className="p-3 text-xs tabular-nums text-muted-foreground">
                              {i + 1}
                            </span>
                            <span className="p-3">
                              <TickerLink
                                ticker={stock.ticker}
                                className={STRETCHED_LINK}
                                title={stock.company}
                              />
                            </span>
                            <span className="p-3 inline-flex items-center gap-2 min-w-0">
                              <StarButton
                                active={isStarred(stock.ticker)}
                                onClick={() => toggleStar(stock.ticker)}
                                size={24}
                                className={ABOVE_STRETCHED_LINK}
                              />
                              <span className="company-link cursor-default truncate">
                                {stock.company}
                              </span>
                            </span>
                            <span className="p-3 text-right font-mono">
                              {formatValue(stock.totalValue)}
                            </span>
                            <span
                              className={`p-3 text-right font-mono text-xs ${isPositiveDelta ? "delta-positive" : "delta-negative"}`}
                            >
                              {isPositiveDelta ? "+" : "−"}
                              {formatValue(Math.abs(stock.totalDeltaValue))}
                            </span>
                            <span className="p-3 text-right font-mono text-xs text-muted-foreground">
                              {stock.holderCount}
                            </span>
                            <span className="p-3 text-right font-mono text-xs">
                              {stock.smartScore !== undefined ? (
                                <SmartScoreBadge score={stock.smartScore} />
                              ) : (
                                <span className="text-muted-foreground">—</span>
                              )}
                            </span>
                            <span className="p-3" aria-hidden="true">
                              <span className="block h-1 rounded-sm bg-muted overflow-hidden">
                                <span
                                  className="block h-full bg-primary"
                                  style={{ width: `${barPct}%` }}
                                />
                              </span>
                            </span>
                          </div>
                        );
                      }}
                    />
                  </div>
                </>
              )}
            </>
          )}
        </TabsContent>

        {/* ── Sectors tab ── (children deferred until tab visited at least once) */}
        <TabsContent value="sectors" className="space-y-4">
          {(visitedTabs.has("sectors") || selectedTab === "sectors") && (
            <>
              {quarterIsError ? (
                <QueryState isError error={quarterError} title="Could not load quarter data" />
              ) : analysisLoading ? (
                <>
                  <span role="status" className="sr-only">
                    Loading sector values…
                  </span>
                  <AnalysisRowsSkeleton kind="value" />
                  <AnalysisRowsSkeleton kind="value" desktop />
                </>
              ) : analysisReady ? (
                <SectorHeatmap
                  onSectorClick={(sector) => {
                    setSectorFilter(sector);
                    setIndustryFilter(null);
                    setValueSort("totalValue", "desc");
                    switchToTab("byvalue");
                  }}
                />
              ) : (
                <p className="text-center text-muted-foreground py-8">No quarter data available.</p>
              )}
              <YFinanceClassificationTreeVisual
                onSelectIndustry={(industry) => {
                  setIndustryFilter(industry);
                  setSectorFilter(null);
                  setValueSort("totalValue", "desc");
                  switchToTab("byvalue");
                }}
              />
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
