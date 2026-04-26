import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
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
import { Search, Loader2, TreePine, SortAsc, TrendingDown, TrendingUp, DollarSign, CandlestickChart, Star } from "lucide-react";
import GICSTreeVisual from "@/components/GICSTreeVisual";
import GICSSectorHeatmap from "@/components/GICSSectorHeatmap";
import { HoldingsTreemap } from "@/components/HoldingsTreemap";
import { useStarred } from "@/hooks/useStarred";
import { StarButton } from "@/components/StarButton";

const ALPHABET = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

export default function StockBrowser() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [activeLetter, setActiveLetter] = useState<string | null>(null);
  const [showAllAlpha, setShowAllAlpha] = useState(false);
  const ALPHA_TOP_N = 1000;
  const [valueSearch, setValueSearch] = useState("");
  const [showAllValue, setShowAllValue] = useState(false);
  const [valueSortKey, setValueSortKey] = useState<"totalValue" | "totalDeltaValue" | "holderCount">("totalValue");
  const [valueSortDir, setValueSortDir] = useState<"asc" | "desc">("desc");
  const VALUE_TOP_N = 50;
  const { starred, toggle: toggleStar, isStarred } = useStarred("stock");

  function toggleValueSort(key: typeof valueSortKey) {
    if (valueSortKey === key) setValueSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setValueSortKey(key); setValueSortDir("desc"); }
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
    return new Set(sorted.slice(0, ALPHA_TOP_N).map((s) => s.ticker));
  }, [quarterData, ALPHA_TOP_N]);

  // Starred stocks
  const starredStocks = useMemo(() => {
    return uniqueStocks.filter((s) => starred.has(s.ticker)).sort((a, b) => a.ticker.localeCompare(b.ticker));
  }, [uniqueStocks, starred]);

  // Alphabetical filtering
  const filtered = useMemo(() => {
    let list = uniqueStocks;
    if (!showAllAlpha && topTickersByValue && !search) {
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
        (s) => s.ticker.toLowerCase().includes(q) || s.company.toLowerCase().includes(q)
      );
    }
    return list.sort((a, b) => a.ticker.localeCompare(b.ticker));
  }, [uniqueStocks, search, activeLetter, showAllAlpha, topTickersByValue]);

  const grouped = useMemo(() => {
    const groups = new Map<string, Stock[]>();
    for (const s of filtered) {
      const letter = /^[A-Z]/i.test(s.ticker) ? s.ticker[0].toUpperCase() : "#";
      const arr = groups.get(letter) || [];
      arr.push(s);
      groups.set(letter, arr);
    }
    return groups;
  }, [filtered]);

  const valueRanked = useMemo(() => {
    let list = [...quarterData];
    list.sort((a, b) => {
      const va = a[valueSortKey];
      const vb = b[valueSortKey];
      return valueSortDir === "desc" ? vb - va : va - vb;
    });
    if (valueSearch) {
      const q = valueSearch.toLowerCase();
      list = list.filter(
        (s) => s.ticker.toLowerCase().includes(q) || s.company.toLowerCase().includes(q)
      );
    }
    return list;
  }, [quarterData, valueSearch, valueSortKey, valueSortDir]);

  const heatmapData = useMemo(() => {
    if (quarterData.length === 0) return [];
    const sorted = [...quarterData].sort((a, b) => b.totalValue - a.totalValue);
    return sorted.slice(0, 20).map((s) => ({
      name: s.ticker,
      company: s.company,
      value: s.totalValue,
      deltaPct: s.delta === Infinity ? 100 : s.delta,
      delta: s.delta === Infinity ? "NEW" : s.delta > 0 ? "INCREASE" : s.delta < 0 ? "DECREASE" : "NO CHANGE",
    }));
  }, [quarterData]);

  const maxValue = useMemo(() => {
    if (quarterData.length === 0) return 1;
    return Math.max(...quarterData.map((s) => s.totalValue)) || 1;
  }, [quarterData]);

  return (
    <div className="space-y-5 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2"><CandlestickChart className="h-6 w-6" /> Stocks</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Browse {uniqueStocks.length.toLocaleString()} tracked securities
        </p>
      </div>

      <Tabs defaultValue={starred.size > 0 ? "starred" : "alphabetical"} className="space-y-4">
        <TabsList>
          {starred.size > 0 && (
            <TabsTrigger value="starred" className="gap-1.5 group">
              <Star className="h-3.5 w-3.5" fill="currentColor" /> Starred
              <span className="ml-1 text-[10px] font-mono bg-primary/20 text-primary group-data-[state=active]:bg-primary-foreground/20 group-data-[state=active]:text-primary-foreground px-1.5 py-0.5 rounded-full leading-none">{starred.size}</span>
            </TabsTrigger>
          )}
          <TabsTrigger value="alphabetical" className="gap-1.5">
            <SortAsc className="h-3.5 w-3.5" /> Alphabetical
          </TabsTrigger>
          <TabsTrigger value="byvalue" className="gap-1.5">
            <DollarSign className="h-3.5 w-3.5" /> By Value
          </TabsTrigger>
          <TabsTrigger value="gics" className="gap-1.5 text-muted-foreground data-[state=active]:text-foreground">
            <TreePine className="h-3.5 w-3.5" /> GICS® Sectors
            <span className="ml-1 text-[9px] font-normal bg-muted text-muted-foreground px-1.5 py-0.5 rounded-full leading-none">Preview</span>
          </TabsTrigger>
        </TabsList>

        {/* ── Starred tab ── */}
        <TabsContent value="starred" className="space-y-4">
          {starredStocks.length === 0 ? (
            <div className="rounded-lg border border-border bg-card p-12 text-center">
              <Star className="h-8 w-8 mx-auto text-muted-foreground/30 mb-3" />
              <p className="text-muted-foreground">No starred stocks yet.</p>
              <p className="text-xs text-muted-foreground/60 mt-1">Click the ★ icon on any stock to add it here.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
              {starredStocks.map((stock) => (
                <div
                  key={stock.ticker}
                  className="kpi-card cursor-pointer py-2.5 px-3"
                  onClick={() => navigate(`/stock/${stock.ticker}`)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-mono font-semibold text-sm text-primary">{stock.ticker}</span>
                      <span className="text-xs text-muted-foreground truncate">{stock.company}</span>
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
            {!showAllAlpha && !search && topTickersByValue && uniqueStocks.length > ALPHA_TOP_N && (
              <button
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => setShowAllAlpha(true)}
              >
                Showing top {ALPHA_TOP_N.toLocaleString()} by value · <span className="underline">Show all {uniqueStocks.length.toLocaleString()}</span>
              </button>
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
                        className="kpi-card cursor-pointer py-2.5 px-3"
                        onClick={() => navigate(`/stock/${stock.ticker}`)}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="font-mono font-semibold text-sm text-primary">{stock.ticker}</span>
                            <span className="text-xs text-muted-foreground truncate">{stock.company}</span>
                          </div>
                          <StarButton active={isStarred(stock.ticker)} onClick={() => toggleStar(stock.ticker)} size={14} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* ── By Value tab ── */}
        <TabsContent value="byvalue" className="space-y-4">
          {!quarterLoading && heatmapData.length > 0 && (
            <div className="rounded-lg border border-border bg-card p-5">
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
            {!showAllValue && !valueSearch && valueRanked.length > VALUE_TOP_N ? (
              <button
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => setShowAllValue(true)}
              >
                Showing top {VALUE_TOP_N} by value · <span className="underline">Show all {quarterData.length.toLocaleString()}</span>
              </button>
            ) : (
              <p className="text-xs text-muted-foreground">
                {latestQuarter.replace("Q", " Q")} · Total institutional holdings value
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
            <div className="rounded-lg border border-border bg-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-[10px] text-muted-foreground uppercase tracking-wider">
                      <th className="text-left p-3 font-medium w-12">#</th>
                      <th className="text-left p-3 font-medium w-20">Ticker</th>
                      <th className="text-left p-3 font-medium">Company</th>
                      <th className="p-3 w-8"></th>
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
                    {(showAllValue ? valueRanked : valueRanked.slice(0, VALUE_TOP_N)).map((stock, i) => {
                      const barPct = (stock.totalValue / maxValue) * 100;
                      const isPositiveDelta = stock.totalDeltaValue >= 0;
                      return (
                        <tr
                          key={stock.ticker}
                          className="data-table-row cursor-pointer"
                          onClick={() => navigate(`/stock/${stock.ticker}`)}
                        >
                          <td className="p-3 font-mono text-xs text-muted-foreground">{i + 1}</td>
                          <td className="p-3 font-mono font-semibold text-sm text-primary">{stock.ticker}</td>
                          <td className="p-3 text-muted-foreground truncate max-w-[200px] cursor-pointer hover:text-foreground transition-colors">{stock.company}</td>
                          <td className="p-3">
                            <StarButton active={isStarred(stock.ticker)} onClick={() => toggleStar(stock.ticker)} size={14} />
                          </td>
                          <td className="p-3 text-right font-mono font-medium">{formatValue(stock.totalValue)}</td>
                          <td className={`p-3 text-right font-mono text-xs ${isPositiveDelta ? "delta-positive" : "delta-negative"}`}>
                            <span className="inline-flex items-center gap-1 justify-end">
                              {isPositiveDelta ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                              {formatValue(Math.abs(stock.totalDeltaValue))}
                            </span>
                          </td>
                          <td className="p-3 text-right font-mono text-xs text-muted-foreground">{stock.holderCount}</td>
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
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </TabsContent>

        {/* ── GICS Sectors tab ── */}
        <TabsContent value="gics" className="space-y-4">
          <GICSSectorHeatmap />
          <GICSTreeVisual />
        </TabsContent>
      </Tabs>
    </div>
  );
}
