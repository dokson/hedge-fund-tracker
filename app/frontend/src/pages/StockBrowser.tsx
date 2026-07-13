import { useState, useMemo, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  getStocks,
  runQuarterAnalysis,
  fetchQuarterAnalysis,
  formatValue,
  type Stock,
  type StockQuarterAnalysis,
} from "@/lib/dataService";
import { smartScoreToneClass, percentileBarClass } from "@/lib/smartScore";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { SearchInput } from "@/components/ui/SearchInput";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  LayoutGrid,
  SortAsc,
  X,
  TrendingDown,
  TrendingUp,
  DollarSign,
  CandlestickChart,
  Gauge,
  Star,
} from "lucide-react";
import SectorHeatmap from "@/components/SectorHeatmap";
import YFinanceClassificationTreeVisual from "@/components/YFinanceClassificationTreeVisual";
import { HoldingsTreemap } from "@/components/HoldingsTreemap";
import { useStarred } from "@/hooks/useStarred";
import { StarButton } from "@/components/StarButton";
import { SmartScoreBadge } from "@/components/SmartScoreBadge";
import { TickerLink } from "@/components/EntityLinks";
import { CompanyLogo } from "@/components/CompanyLogo";
import { matchesQuery } from "@/lib/utils";
import { stockPath } from "@/lib/routes";
import { VirtualList } from "@/components/ui/VirtualList";

const ALPHABET = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
const VALID_TABS = ["score", "starred", "byvalue", "sectors", "alphabetical"] as const;

// Column template for the windowed "Score" grid (kept literal for Tailwind).
const SCORE_GRID_COLS =
  "grid grid-cols-[3rem_5rem_minmax(0,1fr)_6.5rem_minmax(4.5rem,7rem)_minmax(4.5rem,7rem)_minmax(4.5rem,7rem)]";

// Shared column template for the windowed "By Value" grid so the sticky header
// and every virtualized row align. Kept as one literal so Tailwind emits it.
const VALUE_GRID_COLS =
  "grid grid-cols-[3rem_5rem_minmax(0,1fr)_minmax(6.5rem,auto)_minmax(6rem,auto)_4rem_4.5rem_8rem]";

/** Podium accent for the top 3 Score-tab ranks; ranks 4+ stay plain mono text. */
const PODIUM_RANK_CLASS: Record<number, string> = {
  1: "border-amber-500/40 bg-amber-500/10 text-amber-500",
  2: "border-slate-400/40 bg-slate-400/10 text-slate-400",
  3: "border-orange-700/40 bg-orange-700/10 text-orange-700 dark:text-orange-400",
};

function RankBadge({ rank }: { rank: number }) {
  const podiumClass = PODIUM_RANK_CLASS[rank];
  if (!podiumClass) {
    return <span className="font-mono text-xs text-muted-foreground">{rank}</span>;
  }
  return (
    <span
      className={`inline-flex h-5 w-5 items-center justify-center rounded-full border font-mono text-[10px] font-bold ${podiumClass}`}
    >
      {rank}
    </span>
  );
}

/**
 * Inline 0-100 percentile meter for a Smart Score sub-component (Breadth,
 * Momentum, Conviction) — a filled track instead of a bare number, so each
 * row visually reads as "score built from these parts" rather than an
 * unrelated set of stats.
 */
function PercentileBar({ label, value }: { label?: string; value: number | null }) {
  return (
    <div className="flex items-center gap-1.5 min-w-0">
      {label && <span className="metric-label w-20 shrink-0">{label}</span>}
      <div className="h-1 flex-1 min-w-[2rem] rounded-full bg-muted overflow-hidden">
        {value !== null && (
          <div
            className={`h-full rounded-full ${percentileBarClass(value)}`}
            style={{ width: `${value}%` }}
          />
        )}
      </div>
      <span className="font-mono text-xs text-muted-foreground tabular-nums w-6 text-right shrink-0">
        {value === null ? "—" : Math.round(value)}
      </span>
    </div>
  );
}

/**
 * Mobile card for one "By Value" row. The seven-column table can't fit a phone,
 * so below `md` each ranked stock collapses to a card: rank + ticker + star on
 * top, company beneath, a three-up stats footer, and the relative-size bar.
 */
function ValueStockCard({
  stock,
  rank,
  maxValue,
  starred,
  smartScore,
  onToggleStar,
  onOpen,
}: {
  stock: StockQuarterAnalysis;
  rank: number;
  maxValue: number;
  starred: boolean;
  smartScore: number | undefined;
  onToggleStar: () => void;
  onOpen: () => void;
}) {
  const barPct = (stock.totalValue / maxValue) * 100;
  const isPositiveDelta = stock.totalDeltaValue >= 0;
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
      className="surface p-3.5 cursor-pointer"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-mono text-xs text-muted-foreground shrink-0">#{rank}</span>
          <TickerLink ticker={stock.ticker} />
          {smartScore !== undefined && (
            <span
              className={`font-mono text-xs font-semibold shrink-0 ${smartScoreToneClass(smartScore)}`}
            >
              {smartScore.toFixed(1)}
            </span>
          )}
        </div>
        <StarButton active={starred} onClick={onToggleStar} size={16} />
      </div>
      <div className="company-link cursor-default mt-2 text-sm" title={stock.company}>
        {stock.company}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="metric-label">Value</div>
          <div className="font-mono text-sm text-foreground mt-0.5">
            {formatValue(stock.totalValue)}
          </div>
        </div>
        <div>
          <div className="metric-label">Δ Value</div>
          <div
            className={`font-mono text-sm mt-0.5 inline-flex items-center justify-center gap-1 ${isPositiveDelta ? "delta-positive" : "delta-negative"}`}
          >
            {isPositiveDelta ? (
              <TrendingUp className="h-3 w-3" />
            ) : (
              <TrendingDown className="h-3 w-3" />
            )}
            {formatValue(Math.abs(stock.totalDeltaValue))}
          </div>
        </div>
        <div>
          <div className="metric-label">Funds</div>
          <div className="font-mono text-sm text-muted-foreground mt-0.5">{stock.holderCount}</div>
        </div>
      </div>
      <div className="mt-3 h-2 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary/60 transition-all"
          style={{ width: `${barPct}%` }}
        />
      </div>
    </div>
  );
}

export default function StockBrowser() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [activeLetter, setActiveLetter] = useState<string | null>(null);
  const ALPHA_CHUNK = 500;
  // How many top-by-value tickers are revealed in the Alphabetical tab. Bumped
  // in 500-chunk increments via the "Show 500 more" affordance. Resets to one
  // chunk whenever a search or letter filter is applied so the chunking is
  // about scale, not about the active query.
  const [alphaReveal, setAlphaReveal] = useState(ALPHA_CHUNK);
  const [valueSearch, setValueSearch] = useState("");
  const [scoreSearch, setScoreSearch] = useState("");
  const [valueSortKey, setValueSortKey] = useState<
    "totalValue" | "totalDeltaValue" | "holderCount" | "smartScore"
  >("totalValue");
  const [valueSortDir, setValueSortDir] = useState<"asc" | "desc">("desc");
  const [industryFilter, setIndustryFilter] = useState<string | null>(null);
  const [sectorFilter, setSectorFilter] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const { starred, toggle: toggleStar, isStarred } = useStarred("stock");
  const [searchParams, setSearchParams] = useSearchParams();
  // Order of preference: explicit ?tab=... > starred (if any) > score.
  const defaultTab = starred.size > 0 ? "starred" : "score";
  const urlTab = searchParams.get("tab");
  const initialTab =
    urlTab && (VALID_TABS as readonly string[]).includes(urlTab) ? urlTab : defaultTab;
  // Tabs are mounted lazily — children render only after the tab is visited at
  // least once. Once visited, they stay in the tree so switching tabs is instant.
  const [visitedTabs, setVisitedTabs] = useState<Set<string>>(() => new Set([initialTab]));

  // Two effects below sync local state with the URL (external system) — the
  // canonical setState-in-effect use-case. Param consumption in tick 1 + the
  // setActiveTab short-circuit guarantee no cascading renders.
  /* oxlint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const param = searchParams.get("industry");
    if (param) {
      setIndustryFilter(param);
      setSectorFilter(null);
      setActiveTab("byvalue");
      setVisitedTabs((prev) => (prev.has("byvalue") ? prev : new Set(prev).add("byvalue")));
      // Consume the industry param but keep the tab param if present.
      const next = new URLSearchParams(searchParams);
      next.delete("industry");
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const urlTabNow = searchParams.get("tab");
    const target =
      urlTabNow && (VALID_TABS as readonly string[]).includes(urlTabNow) ? urlTabNow : defaultTab;
    setActiveTab((current) => (current === target ? current : target));
    setVisitedTabs((prev) => (prev.has(target) ? prev : new Set(prev).add(target)));
  }, [searchParams, defaultTab]);
  /* oxlint-enable react-hooks/set-state-in-effect */

  // Progressive reveal: render the first chunk on mount, hydrate the rest after
  // the browser is idle so the initial INP isn't blocked by 500 cards of React
  // tree + <img> elements. Reset whenever the filtered list churns.
  const ALPHA_INITIAL_RENDER = 80;
  const [renderCount, setRenderCount] = useState(ALPHA_INITIAL_RENDER);

  function toggleValueSort(key: typeof valueSortKey) {
    if (valueSortKey === key) setValueSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else {
      setValueSortKey(key);
      setValueSortDir("desc");
    }
  }
  function valueSortIndicator(key: typeof valueSortKey) {
    if (valueSortKey !== key) return null;
    return valueSortDir === "desc" ? " ↓" : " ↑";
  }

  const { data: stocks = [], isLoading } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
  });

  const { latestQuarter } = useAvailableQuarters();
  const { data: quarterData = [], isLoading: quarterLoading } = useQuery({
    queryKey: ["quarterAnalysis", latestQuarter],
    queryFn: async () => {
      const fromBackend = await fetchQuarterAnalysis(latestQuarter!);
      return fromBackend ?? (await runQuarterAnalysis(latestQuarter!));
    },
    enabled: !!latestQuarter,
    staleTime: 10 * 60 * 1000,
  });

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

  // Starred stocks
  const starredStocks = useMemo(() => {
    return uniqueStocks
      .filter((s) => starred.has(s.ticker))
      .sort((a, b) => a.ticker.localeCompare(b.ticker));
  }, [uniqueStocks, starred]);

  // Alphabetical filtering
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
    list.sort(
      (a, b) => (b.smartScore ?? 0) - (a.smartScore ?? 0) || a.ticker.localeCompare(b.ticker),
    );
    if (scoreSearch) {
      list = list.filter((s) => matchesQuery(scoreSearch, s.ticker, s.company));
    }
    return list;
  }, [quarterData, uniqueStocks, scoreSearch]);

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

  // Shared by the TabsList's onValueChange and any programmatic tab switch
  // (e.g. clicking a sector/industry cell) — mounts the tab (lazy-mount set),
  // resets the alphabetical chunk cap, and syncs the URL, all in one place so
  // a programmatic switch can never skip a step the user-driven one does.
  function switchToTab(value: string) {
    setActiveTab(value);
    setVisitedTabs((prev) => (prev.has(value) ? prev : new Set(prev).add(value)));
    setAlphaReveal(ALPHA_CHUNK);
    const next = new URLSearchParams(searchParams);
    if (value === defaultTab) next.delete("tab");
    else next.set("tab", value);
    setSearchParams(next, { replace: false });
  }

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div>
        <span className="eyebrow">Tracked universe</span>
        <h1 className="page-title mt-1.5">
          <CandlestickChart className="page-title-icon" /> Stocks
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Browse {uniqueStocks.length.toLocaleString()} tracked securities
        </p>
      </div>

      <Tabs value={activeTab ?? initialTab} onValueChange={switchToTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="score" className="gap-1.5">
            <Gauge className="h-3.5 w-3.5" /> Score
          </TabsTrigger>
          {starred.size > 0 && (
            <TabsTrigger value="starred" className="gap-1.5 group">
              <Star className="h-3.5 w-3.5" fill="currentColor" /> Starred
              <span className="ml-1 text-[10px] font-mono bg-primary/20 text-primary group-data-[state=active]:bg-primary-foreground/20 group-data-[state=active]:text-primary-foreground px-1.5 py-0.5 rounded-full leading-none">
                {starred.size}
              </span>
            </TabsTrigger>
          )}
          <TabsTrigger value="byvalue" className="gap-1.5">
            <DollarSign className="h-3.5 w-3.5" /> Value
          </TabsTrigger>
          <TabsTrigger value="sectors" className="gap-1.5">
            <LayoutGrid className="h-3.5 w-3.5" /> Sectors
          </TabsTrigger>
          <TabsTrigger value="alphabetical" className="gap-1.5">
            <SortAsc className="h-3.5 w-3.5" /> Alphabetical
          </TabsTrigger>
        </TabsList>

        {/* ── Starred tab ── */}
        <TabsContent value="starred" className="space-y-4">
          {starredStocks.length === 0 ? (
            <EmptyState
              icon={Star}
              title="No starred stocks yet."
              description="Click the ★ icon on any stock to add it here."
            />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
              {starredStocks.map((stock) => (
                <div
                  key={stock.ticker}
                  role="button"
                  tabIndex={0}
                  className="kpi-card cursor-pointer py-2.5 px-3"
                  onClick={() => navigate(stockPath(stock.ticker))}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      void navigate(stockPath(stock.ticker));
                    }
                  }}
                >
                  <div className="flex items-center gap-3">
                    <CompanyLogo ticker={stock.ticker} size={28} className="rounded-md" />
                    <div className="flex flex-col min-w-0 leading-tight flex-1">
                      <span className="font-mono font-semibold text-sm text-primary">
                        {stock.ticker}
                      </span>
                      <span className="company-link text-xs cursor-default" title={stock.company}>
                        {stock.company}
                      </span>
                    </div>
                    <StarButton active={true} onClick={() => toggleStar(stock.ticker)} size={14} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* ── Alphabetical tab ── */}
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
                <span aria-hidden="true">·</span>
                <button
                  type="button"
                  className="underline hover:text-foreground transition-colors"
                  onClick={() =>
                    setAlphaReveal((n) => Math.min(n + ALPHA_CHUNK, uniqueStocks.length))
                  }
                >
                  Show {ALPHA_CHUNK.toLocaleString()} more
                </button>
                <span aria-hidden="true">·</span>
                <button
                  type="button"
                  className="underline hover:text-foreground transition-colors"
                  onClick={() => setAlphaReveal(uniqueStocks.length)}
                >
                  Show all
                </button>
              </div>
            )}
          </div>

          <div className="grid grid-cols-9 sm:grid-cols-[repeat(28,1fr)] gap-1 sm:gap-0.5">
            <button
              onClick={() => setActiveLetter(null)}
              className={`py-1.5 text-xs font-mono rounded transition-colors ${
                activeLetter === null
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              All
            </button>
            {ALPHABET.map((letter) => (
              <button
                key={letter}
                onClick={() => setActiveLetter(activeLetter === letter ? null : letter)}
                className={`py-1.5 text-xs font-mono rounded transition-colors ${
                  activeLetter === letter
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
              >
                {letter}
              </button>
            ))}
          </div>

          {isLoading ? (
            <LoadingState message="Loading stocks…" />
          ) : filtered.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No stocks match your search.</p>
          ) : (
            <div className="space-y-6">
              {[...grouped.entries()].map(([letter, items]) => (
                <div key={letter}>
                  <h2 className="text-sm font-bold text-muted-foreground mb-2 sticky top-0 bg-background py-1 border-b border-border">
                    {letter}
                    <span className="ml-2 text-xs font-normal">({items.length})</span>
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
                    {items.map((stock) => (
                      <div
                        key={`${stock.cusip}-${stock.ticker}`}
                        role="button"
                        tabIndex={0}
                        // content-visibility:auto lets the browser skip layout
                        // and paint for off-screen cards; intrinsic-size keeps
                        // the scroll height stable.
                        style={{
                          contentVisibility: "auto",
                          containIntrinsicSize: "auto 56px",
                        }}
                        className="kpi-card cursor-pointer py-2.5 px-3"
                        onClick={() => navigate(stockPath(stock.ticker))}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            void navigate(stockPath(stock.ticker));
                          }
                        }}
                      >
                        <div className="flex items-center gap-3">
                          <CompanyLogo ticker={stock.ticker} size={28} className="rounded-md" />
                          <div className="flex flex-col min-w-0 leading-tight flex-1">
                            <span className="font-mono font-semibold text-sm text-primary">
                              {stock.ticker}
                            </span>
                            <span
                              className="company-link text-xs cursor-default"
                              title={stock.company}
                            >
                              {stock.company}
                            </span>
                          </div>
                          <StarButton
                            active={isStarred(stock.ticker)}
                            onClick={() => toggleStar(stock.ticker)}
                            size={14}
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
          {visitedTabs.has("score") && (
            <>
              <div className="flex flex-col sm:flex-row gap-4 items-start justify-between">
                <SearchInput
                  label="Search ticker or company"
                  value={scoreSearch}
                  onChange={(e) => setScoreSearch(e.target.value)}
                  wrapperClassName="w-full sm:w-72"
                />
                <p className="text-xs text-muted-foreground">
                  {scoreRanked.length.toLocaleString()} stocks ·{" "}
                  {latestQuarter?.replace("Q", " Q") ?? ""} · Institutional signals only
                </p>
              </div>

              {/* Mobile: windowed card list */}
              <VirtualList
                className="md:hidden max-h-[70vh] pr-1"
                items={scoreRanked}
                estimateSize={92}
                getKey={(s) => s.ticker}
                renderItem={(s, i) => (
                  <div className="pb-3">
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => navigate(stockPath(s.ticker))}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          void navigate(stockPath(s.ticker));
                        }
                      }}
                      className="surface p-3.5 cursor-pointer"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 min-w-0">
                          <RankBadge rank={i + 1} />
                          <TickerLink ticker={s.ticker} />
                        </div>
                        <SmartScoreBadge score={s.smartScore ?? 1} size="sm" />
                      </div>
                      <div className="company-link cursor-default mt-2 text-sm" title={s.company}>
                        {s.company}
                      </div>
                      <div className="mt-3 space-y-1.5">
                        <PercentileBar label="Breadth" value={s.scoreBreadth ?? null} />
                        <PercentileBar label="Momentum" value={s.scoreMomentum ?? null} />
                        <PercentileBar label="Conviction" value={s.scoreConviction ?? null} />
                      </div>
                    </div>
                  </div>
                )}
              />

              {/* Desktop: windowed grid "table" */}
              <div className="surface overflow-hidden hidden md:block">
                <div
                  className={`${SCORE_GRID_COLS} items-center border-b border-border text-[10px] text-muted-foreground uppercase tracking-wider`}
                >
                  <span className="text-left p-3 font-medium">#</span>
                  <span className="text-left p-3 font-medium">Ticker</span>
                  <span className="text-left p-3 font-medium">Company</span>
                  <span className="text-right p-3 pr-4 font-medium">
                    <span className="inline-flex items-center justify-end gap-1">
                      Score
                      <InfoTooltip text="Composite 1-10 score: the mean of the Breadth, Momentum and Conviction percentiles, rescaled. Computed on the current quarter's merged view (13F + recent 13D/G and Form 4)." />
                    </span>
                  </span>
                  <span className="text-left p-3 pl-4 font-medium">
                    <span className="inline-flex items-center gap-1">
                      Breadth
                      <InfoTooltip text="Percentile rank of how many tracked funds hold the stock (Holder Count) — 0 to 100." />
                    </span>
                  </span>
                  <span className="text-left p-3 pl-4 font-medium">
                    <span className="inline-flex items-center gap-1">
                      Momentum
                      <InfoTooltip text="Percentile rank of net institutional buying pressure (Net Buyers) — 0 to 100." />
                    </span>
                  </span>
                  <span className="text-left p-3 pl-4 font-medium">
                    <span className="inline-flex items-center gap-1">
                      Conviction
                      <InfoTooltip text="Percentile rank of average portfolio allocation across holders (Avg Portfolio %), plus a capped bonus per high-conviction new entry — 0 to 100." />
                    </span>
                  </span>
                </div>
                <VirtualList
                  className="max-h-[70vh]"
                  items={scoreRanked}
                  estimateSize={45}
                  getKey={(s) => s.ticker}
                  renderItem={(s, i) => (
                    <div
                      role="button"
                      tabIndex={0}
                      aria-label={`View ${s.ticker} details`}
                      className={`data-table-row cursor-pointer text-sm ${SCORE_GRID_COLS} items-center`}
                      onClick={() => navigate(stockPath(s.ticker))}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          void navigate(stockPath(s.ticker));
                        }
                      }}
                    >
                      <span className="p-3 flex items-center">
                        <RankBadge rank={i + 1} />
                      </span>
                      <span className="p-3">
                        <TickerLink ticker={s.ticker} />
                      </span>
                      <span className="p-3 inline-flex items-center gap-2 min-w-0">
                        <StarButton
                          active={isStarred(s.ticker)}
                          onClick={() => toggleStar(s.ticker)}
                          size={14}
                        />
                        <span className="company-link cursor-default truncate" title={s.company}>
                          {s.company}
                        </span>
                      </span>
                      <span className="p-3 text-right">
                        <SmartScoreBadge score={s.smartScore ?? 1} size="sm" />
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
              </div>
            </>
          )}
        </TabsContent>

        <TabsContent value="byvalue" className="space-y-4">
          {!visitedTabs.has("byvalue") ? null : (
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
                    className="inline-flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/10 text-primary px-2.5 py-0.5 text-xs font-medium hover:bg-primary/15 transition-colors"
                  >
                    {industryFilter ?? sectorFilter}
                    <X className="h-3 w-3" aria-label="Clear filter" />
                  </button>
                  <span className="text-xs text-muted-foreground">
                    · {valueRanked.length} stock{valueRanked.length === 1 ? "" : "s"}
                  </span>
                </div>
              )}
              {!quarterLoading && heatmapData.length > 0 && !industryFilter && !sectorFilter && (
                <div className="surface p-5">
                  <h3 className="section-title mb-3 text-sm">Top 20 by Institutional Value</h3>
                  <HoldingsTreemap
                    data={heatmapData}
                    onClickTicker={(t) => navigate(stockPath(t))}
                    height={300}
                  />
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
                  {valueRanked.length.toLocaleString()} stocks ·{" "}
                  {latestQuarter?.replace("Q", " Q") ?? ""} · Total institutional holdings value
                </p>
              </div>

              {quarterLoading ? (
                <LoadingState message="Loading quarter data…" />
              ) : valueRanked.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">No data available.</p>
              ) : (
                <>
                  {/* Mobile: windowed card list */}
                  <VirtualList
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
                          onOpen={() => navigate(stockPath(stock.ticker))}
                        />
                      </div>
                    )}
                  />

                  {/* Desktop: windowed grid "table" (header outside the scroll area) */}
                  <div className="surface overflow-hidden hidden md:block">
                    <div
                      className={`${VALUE_GRID_COLS} items-center border-b border-border text-[10px] text-muted-foreground uppercase tracking-wider`}
                    >
                      <span className="text-left p-3 font-medium">#</span>
                      <span className="text-left p-3 font-medium">Ticker</span>
                      <span className="text-left p-3 font-medium">Company</span>
                      <button
                        type="button"
                        className="text-right p-3 font-medium uppercase cursor-pointer hover:text-foreground whitespace-nowrap"
                        onClick={() => toggleValueSort("totalValue")}
                      >
                        Total Value{valueSortIndicator("totalValue")}
                      </button>
                      <button
                        type="button"
                        className="text-right p-3 font-medium uppercase cursor-pointer hover:text-foreground whitespace-nowrap"
                        onClick={() => toggleValueSort("totalDeltaValue")}
                      >
                        Δ Value{valueSortIndicator("totalDeltaValue")}
                      </button>
                      <button
                        type="button"
                        className="text-right p-3 font-medium uppercase cursor-pointer hover:text-foreground whitespace-nowrap"
                        onClick={() => toggleValueSort("holderCount")}
                      >
                        Funds{valueSortIndicator("holderCount")}
                      </button>
                      <button
                        type="button"
                        className="text-right p-3 font-medium uppercase cursor-pointer hover:text-foreground whitespace-nowrap"
                        onClick={() => toggleValueSort("smartScore")}
                        title="Smart Score: composite of institutional and analyst signals (1-10)"
                      >
                        Score{valueSortIndicator("smartScore")}
                      </button>
                      <span className="p-3 font-medium">Relative Size</span>
                    </div>
                    <VirtualList
                      className="max-h-[70vh]"
                      items={valueRanked}
                      estimateSize={45}
                      getKey={(stock) => stock.ticker}
                      renderItem={(stock, i) => {
                        const barPct = (stock.totalValue / maxValue) * 100;
                        const isPositiveDelta = stock.totalDeltaValue >= 0;
                        return (
                          <div
                            role="button"
                            tabIndex={0}
                            aria-label={`View ${stock.ticker} details`}
                            className={`data-table-row cursor-pointer text-sm ${VALUE_GRID_COLS} items-center`}
                            onClick={() => navigate(stockPath(stock.ticker))}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault();
                                void navigate(stockPath(stock.ticker));
                              }
                            }}
                          >
                            <span className="p-3 font-mono text-xs text-muted-foreground">
                              {i + 1}
                            </span>
                            <span className="p-3">
                              <TickerLink ticker={stock.ticker} />
                            </span>
                            <span className="p-3 inline-flex items-center gap-2 min-w-0">
                              <StarButton
                                active={isStarred(stock.ticker)}
                                onClick={() => toggleStar(stock.ticker)}
                                size={14}
                              />
                              <span
                                className="company-link cursor-default truncate"
                                title={stock.company}
                              >
                                {stock.company}
                              </span>
                            </span>
                            <span className="p-3 text-right font-mono font-medium">
                              {formatValue(stock.totalValue)}
                            </span>
                            <span
                              className={`p-3 text-right font-mono text-xs ${isPositiveDelta ? "delta-positive" : "delta-negative"}`}
                            >
                              <span className="inline-flex items-center gap-1 justify-end">
                                {isPositiveDelta ? (
                                  <TrendingUp className="h-3 w-3" />
                                ) : (
                                  <TrendingDown className="h-3 w-3" />
                                )}
                                {formatValue(Math.abs(stock.totalDeltaValue))}
                              </span>
                            </span>
                            <span className="p-3 text-right font-mono text-xs text-muted-foreground">
                              {stock.holderCount}
                            </span>
                            <span className="p-3 text-right font-mono text-xs">
                              {stock.smartScore !== undefined ? (
                                <span
                                  className={`font-semibold ${smartScoreToneClass(stock.smartScore)}`}
                                >
                                  {stock.smartScore.toFixed(1)}
                                </span>
                              ) : (
                                <span className="text-muted-foreground">—</span>
                              )}
                            </span>
                            <span className="p-3">
                              <span className="block h-2 rounded-full bg-muted overflow-hidden">
                                <span
                                  className="block h-full rounded-full bg-primary/60 transition-all"
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
          {visitedTabs.has("sectors") && (
            <>
              <SectorHeatmap
                onSectorClick={(sector) => {
                  setSectorFilter(sector);
                  setIndustryFilter(null);
                  setValueSortKey("totalValue");
                  setValueSortDir("desc");
                  switchToTab("byvalue");
                }}
              />
              <YFinanceClassificationTreeVisual
                onSelectIndustry={(industry) => {
                  setIndustryFilter(industry);
                  setSectorFilter(null);
                  setValueSortKey("totalValue");
                  setValueSortDir("desc");
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
