import { useState, useMemo, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  getStocks,
  runQuarterAnalysis,
  fetchQuarterAnalysis,
  formatValue,
  type Stock,
} from "@/lib/dataService";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Search,
  Loader2,
  LayoutGrid,
  SortAsc,
  X,
  TrendingDown,
  TrendingUp,
  DollarSign,
  CandlestickChart,
  Star,
} from "lucide-react";
import SectorHeatmap from "@/components/SectorHeatmap";
import YFinanceClassificationTreeVisual from "@/components/YFinanceClassificationTreeVisual";
import { HoldingsTreemap } from "@/components/HoldingsTreemap";
import { useStarred } from "@/hooks/useStarred";
import { StarButton } from "@/components/StarButton";
import { TickerLink } from "@/components/EntityLinks";
import { CompanyLogo } from "@/components/CompanyLogo";

const ALPHABET = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
const VALID_TABS = ["starred", "byvalue", "sectors", "alphabetical"] as const;

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
  const VALUE_CHUNK = 500;
  const [valueReveal, setValueReveal] = useState(VALUE_CHUNK);
  const [valueSortKey, setValueSortKey] = useState<
    "totalValue" | "totalDeltaValue" | "holderCount"
  >("totalValue");
  const [valueSortDir, setValueSortDir] = useState<"asc" | "desc">("desc");
  const [industryFilter, setIndustryFilter] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const { starred, toggle: toggleStar, isStarred } = useStarred("stock");
  const [searchParams, setSearchParams] = useSearchParams();
  // Order of preference: explicit ?tab=... > starred (if any) > byvalue.
  const defaultTab = starred.size > 0 ? "starred" : "byvalue";
  const urlTab = searchParams.get("tab");
  const initialTab =
    urlTab && (VALID_TABS as readonly string[]).includes(urlTab) ? urlTab : defaultTab;
  // Tabs are mounted lazily — children render only after the tab is visited at
  // least once. Once visited, they stay in the tree so switching tabs is instant.
  const [visitedTabs, setVisitedTabs] = useState<Set<string>>(() => new Set([initialTab]));

  // Two effects below sync local state with the URL (external system) — the
  // canonical setState-in-effect use-case. Param consumption in tick 1 + the
  // setActiveTab short-circuit guarantee no cascading renders.
  /* eslint-disable @eslint-react/set-state-in-effect, react-hooks/set-state-in-effect */
  useEffect(() => {
    const param = searchParams.get("industry");
    if (param) {
      setIndustryFilter(param);
      setActiveTab("byvalue");
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
  /* eslint-enable @eslint-react/set-state-in-effect, react-hooks/set-state-in-effect */

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
      const q = search.toLowerCase();
      list = list.filter(
        (s) => s.ticker.toLowerCase().includes(q) || s.company.toLowerCase().includes(q),
      );
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

  // Hydrate the remaining cards once the browser is idle. The setTimeout
  // fallback is paired with clearTimeout via `cancel` in the cleanup return —
  // the linter can't trace the indirection through the `idle` / `cancel` refs.
  useEffect(() => {
    if (renderCount >= filtered.length) return;
    const idle =
      "requestIdleCallback" in window
        ? window.requestIdleCallback
        : (cb: IdleRequestCallback) =>
            // eslint-disable-next-line @eslint-react/web-api-no-leaked-timeout
            window.setTimeout(
              () => cb({ didTimeout: false, timeRemaining: () => 0 } as IdleDeadline),
              0,
            );
    const cancel = "cancelIdleCallback" in window ? window.cancelIdleCallback : window.clearTimeout;
    const handle = idle(() => setRenderCount(filtered.length));
    return () => cancel(handle as number);
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

  // Ticker → industry lookup, derived from stocks.csv (joined with sector_hierarchy
  // inside getStocks). Used to filter the By Value table when the user clicks an
  // industry in the Sectors tab.
  const tickerIndustry = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of stocks) {
      if (s.industry && !map.has(s.ticker)) map.set(s.ticker, s.industry);
    }
    return map;
  }, [stocks]);

  const valueRanked = useMemo(() => {
    let list = [...quarterData];
    if (industryFilter) {
      list = list.filter((s) => tickerIndustry.get(s.ticker) === industryFilter);
    }
    list.sort((a, b) => {
      const va = a[valueSortKey];
      const vb = b[valueSortKey];
      return valueSortDir === "desc" ? vb - va : va - vb;
    });
    if (valueSearch) {
      const q = valueSearch.toLowerCase();
      list = list.filter(
        (s) => s.ticker.toLowerCase().includes(q) || s.company.toLowerCase().includes(q),
      );
    }
    return list;
  }, [quarterData, valueSearch, valueSortKey, valueSortDir, industryFilter, tickerIndustry]);

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

      <Tabs
        value={activeTab ?? initialTab}
        onValueChange={(value) => {
          setActiveTab(value);
          setVisitedTabs((prev) => (prev.has(value) ? prev : new Set(prev).add(value)));
          // Switching tabs resets the chunk caps to one page so a returning
          // user never lands on a heavy 11k-card DOM left behind from before.
          setAlphaReveal(ALPHA_CHUNK);
          setValueReveal(VALUE_CHUNK);
          // Reflect the active tab in the URL so browser back/forward navigate
          // between views. Skip the param when it matches the default to keep
          // /stocks tidy.
          const next = new URLSearchParams(searchParams);
          if (value === defaultTab) next.delete("tab");
          else next.set("tab", value);
          setSearchParams(next, { replace: false });
        }}
        className="space-y-4"
      >
        <TabsList>
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
            <div className="surface p-12 text-center">
              <Star className="h-8 w-8 mx-auto text-muted-foreground/30 mb-3" />
              <p className="text-muted-foreground">No starred stocks yet.</p>
              <p className="text-xs text-muted-foreground/60 mt-1">
                Click the ★ icon on any stock to add it here.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
              {starredStocks.map((stock) => (
                <div
                  key={stock.ticker}
                  role="button"
                  tabIndex={0}
                  className="kpi-card cursor-pointer py-2.5 px-3"
                  onClick={() => navigate(`/stock/${stock.ticker}`)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      navigate(`/stock/${stock.ticker}`);
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
            <div className="relative w-72">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search ticker or company…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 bg-card border-border"
              />
            </div>
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

          <div className="grid grid-cols-[repeat(28,1fr)] gap-0.5">
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
            <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
              <Loader2 className="h-5 w-5 animate-spin" /> Loading stocks…
            </div>
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
                        onClick={() => navigate(`/stock/${stock.ticker}`)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            navigate(`/stock/${stock.ticker}`);
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
        <TabsContent value="byvalue" className="space-y-4">
          {!visitedTabs.has("byvalue") ? null : (
            <>
              {industryFilter && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-muted-foreground">Filtered by industry:</span>
                  <button
                    type="button"
                    onClick={() => setIndustryFilter(null)}
                    className="inline-flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/10 text-primary px-2.5 py-0.5 text-xs font-medium hover:bg-primary/15 transition-colors"
                  >
                    {industryFilter}
                    <X className="h-3 w-3" aria-label="Clear industry filter" />
                  </button>
                  <span className="text-xs text-muted-foreground">
                    · {valueRanked.length} stock{valueRanked.length === 1 ? "" : "s"}
                  </span>
                </div>
              )}
              {!quarterLoading && heatmapData.length > 0 && !industryFilter && (
                <div className="surface p-5">
                  <h3 className="section-title mb-3 text-sm">Top 20 by Institutional Value</h3>
                  <HoldingsTreemap
                    data={heatmapData}
                    onClickTicker={(t) => navigate(`/stock/${t}`)}
                    height={300}
                  />
                </div>
              )}
              <div className="flex flex-col sm:flex-row gap-4 items-start justify-between">
                <div className="relative w-72">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search ticker or company…"
                    value={valueSearch}
                    onChange={(e) => setValueSearch(e.target.value)}
                    className="pl-9 bg-card border-border"
                  />
                </div>
                {!valueSearch && valueRanked.length > valueReveal ? (
                  <div className="text-xs text-muted-foreground flex items-center gap-3 flex-wrap">
                    <span>
                      Showing top {valueReveal.toLocaleString()} of{" "}
                      {valueRanked.length.toLocaleString()} by value
                    </span>
                    <span aria-hidden="true">·</span>
                    <button
                      type="button"
                      className="underline hover:text-foreground transition-colors"
                      onClick={() =>
                        setValueReveal((n) => Math.min(n + VALUE_CHUNK, valueRanked.length))
                      }
                    >
                      Show {VALUE_CHUNK.toLocaleString()} more
                    </button>
                    <span aria-hidden="true">·</span>
                    <button
                      type="button"
                      className="underline hover:text-foreground transition-colors"
                      onClick={() => setValueReveal(valueRanked.length)}
                    >
                      Show all
                    </button>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    {latestQuarter?.replace("Q", " Q") ?? ""} · Total institutional holdings value
                  </p>
                )}
              </div>

              {quarterLoading ? (
                <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
                  <Loader2 className="h-5 w-5 animate-spin" /> Loading quarter data…
                </div>
              ) : valueRanked.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">No data available.</p>
              ) : (
                <div className="surface overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border text-[10px] text-muted-foreground uppercase tracking-wider">
                          <th className="text-left p-3 font-medium w-12">#</th>
                          <th className="text-left p-3 font-medium w-20">Ticker</th>
                          <th className="text-left p-3 font-medium">Company</th>
                          <th
                            className="text-right p-3 font-medium cursor-pointer hover:text-foreground whitespace-nowrap"
                            onClick={() => toggleValueSort("totalValue")}
                          >
                            Total Value{valueSortIndicator("totalValue")}
                          </th>
                          <th
                            className="text-right p-3 font-medium cursor-pointer hover:text-foreground whitespace-nowrap"
                            onClick={() => toggleValueSort("totalDeltaValue")}
                          >
                            Δ Value{valueSortIndicator("totalDeltaValue")}
                          </th>
                          <th
                            className="text-right p-3 font-medium cursor-pointer hover:text-foreground whitespace-nowrap"
                            onClick={() => toggleValueSort("holderCount")}
                          >
                            Funds{valueSortIndicator("holderCount")}
                          </th>
                          <th className="p-3 font-medium w-32">Relative Size</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(valueSearch ? valueRanked : valueRanked.slice(0, valueReveal)).map(
                          (stock, i) => {
                            const barPct = (stock.totalValue / maxValue) * 100;
                            const isPositiveDelta = stock.totalDeltaValue >= 0;
                            return (
                              <tr
                                key={stock.ticker}
                                className="data-table-row cursor-pointer"
                                onClick={() => navigate(`/stock/${stock.ticker}`)}
                              >
                                <td className="p-3 font-mono text-xs text-muted-foreground">
                                  {i + 1}
                                </td>
                                <td className="p-3">
                                  <TickerLink ticker={stock.ticker} />
                                </td>
                                <td className="p-3">
                                  <span className="inline-flex items-center gap-2 align-middle">
                                    <StarButton
                                      active={isStarred(stock.ticker)}
                                      onClick={() => toggleStar(stock.ticker)}
                                      size={14}
                                    />
                                    <span
                                      className="company-link cursor-default max-w-[180px] xl:max-w-[260px]"
                                      title={stock.company}
                                    >
                                      {stock.company}
                                    </span>
                                  </span>
                                </td>
                                <td className="p-3 text-right font-mono font-medium">
                                  {formatValue(stock.totalValue)}
                                </td>
                                <td
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
                                </td>
                                <td className="p-3 text-right font-mono text-xs text-muted-foreground">
                                  {stock.holderCount}
                                </td>
                                <td className="p-3">
                                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                                    <div
                                      className="h-full rounded-full bg-primary/60 transition-all"
                                      style={{ width: `${barPct}%` }}
                                    />
                                  </div>
                                </td>
                              </tr>
                            );
                          },
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </TabsContent>

        {/* ── Sectors tab ── (children deferred until tab visited at least once) */}
        <TabsContent value="sectors" className="space-y-4">
          {visitedTabs.has("sectors") && (
            <>
              <SectorHeatmap />
              <YFinanceClassificationTreeVisual
                onSelectIndustry={(industry) => {
                  setIndustryFilter(industry);
                  setValueSortKey("totalValue");
                  setValueSortDir("desc");
                  setActiveTab("byvalue");
                }}
              />
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
