import { useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { isQuarter } from "@/lib/quarters";
import { useQuery } from "@tanstack/react-query";
import {
  getHedgeFunds,
  getStocks,
  getFundQuarterlyHoldings,
  getFundAvailableQuarters,
  parseValueString,
  type HedgeFund,
  type QuarterlyHolding,
} from "@/lib/dataService";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { TickerLink, formatFundName } from "@/components/EntityLinks";
import { toInitCap } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { HoldingsTreemap } from "@/components/HoldingsTreemap";

import { Search, ArrowLeft, Loader2, Wallet, Filter, SortAsc, DollarSign, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useStarred } from "@/hooks/useStarred";
import { StarButton } from "@/components/StarButton";


// ────────────────────────── Fund Grid ──────────────────────────

function FundGrid() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const { starred, toggle: toggleStar, isStarred } = useStarred("fund");
  const [tab, setTab] = useState<"starred" | "alphabetical" | "byvalue">(() => starred.size > 0 ? "starred" : "alphabetical");

  const { data: funds = [], isLoading } = useQuery({
    queryKey: ["hedgeFunds"],
    queryFn: getHedgeFunds,
  });

  // Load AUM for each fund (latest quarter)
  const { data: fundAumMap = new Map<string, number>() } = useQuery({
    queryKey: ["fundAumMap", funds.length],
    queryFn: async () => {
      const aumMap = new Map<string, number>();
      await Promise.all(
        funds.map(async (fund) => {
          try {
            const quarters = await getFundAvailableQuarters(fund.fund);
            if (quarters.length === 0) return;
            const latest = quarters[quarters.length - 1];
            const holdings = await getFundQuarterlyHoldings(latest, fund.fund);
            const total = holdings
              .filter((h) => h.cusip !== "Total")
              .reduce((sum, h) => sum + parseValue(h.value), 0);
            aumMap.set(fund.fund, total);
          } catch { /* skip */ }
        })
      );
      return aumMap;
    },
    enabled: funds.length > 0,
  });

  const starredFunds = useMemo(() => {
    return funds.filter((f) => starred.has(f.fund)).sort((a, b) => a.denomination.localeCompare(b.denomination));
  }, [funds, starred]);

  const filtered = useMemo(() => {
    let list = funds;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (f) =>
          f.fund.toLowerCase().includes(q) ||
          f.manager.toLowerCase().includes(q) ||
          f.denomination.toLowerCase().includes(q)
      );
    }
    if (tab === "byvalue") {
      list = [...list].sort((a, b) => (fundAumMap.get(b.fund) || 0) - (fundAumMap.get(a.fund) || 0));
    } else {
      list = [...list].sort((a, b) => a.denomination.localeCompare(b.denomination));
    }
    return list;
  }, [funds, search, tab, fundAumMap]);

  return (
    <div className="space-y-5 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2"><Wallet className="h-6 w-6" /> Hedge Fund Portfolios</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Browse {funds.length} tracked institutional investors
        </p>
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
        <div className="flex flex-wrap items-center gap-3">
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
              <DollarSign className="h-3.5 w-3.5" /> By AUM
            </TabsTrigger>
          </TabsList>
          <div className="relative w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search fund or manager…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 bg-card border-border"
            />
          </div>
        </div>

        {/* Starred tab */}
        <TabsContent value="starred">
          {starredFunds.length === 0 ? (
            <div className="rounded-lg border border-border bg-card p-12 text-center mt-4">
              <Star className="h-8 w-8 mx-auto text-muted-foreground/30 mb-3" />
              <p className="text-muted-foreground">No starred funds yet.</p>
              <p className="text-xs text-muted-foreground/60 mt-1">Click the ★ icon on any fund to add it here.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mt-4">
              {starredFunds.map((fund) => {
                const aum = fundAumMap.get(fund.fund);
                return (
                  <div
                    key={fund.cik}
                    className="kpi-card cursor-pointer"
                    onClick={() => navigate(`/funds/${encodeURIComponent(fund.fund)}`)}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold truncate">{fund.denomination}</p>
                        <p className="text-xs text-muted-foreground truncate">{fund.manager}</p>
                      </div>
                      <StarButton active={true} onClick={() => toggleStar(fund.fund)} size={14} className="mt-0.5 shrink-0" />
                    </div>
                    {aum !== undefined && (
                      <p className="text-xs font-mono text-muted-foreground mt-1.5">
                        AUM {aum > 0 ? formatValue(aum) : "$0"}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </TabsContent>

        {isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading funds…
          </div>
        ) : (
          <>
            <TabsContent value="alphabetical">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mt-4">
                {filtered.map((fund) => {
                  const aum = fundAumMap.get(fund.fund);
                  return (
                    <div
                      key={fund.cik}
                      className="kpi-card cursor-pointer"
                      onClick={() => navigate(`/funds/${encodeURIComponent(fund.fund)}`)}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold truncate">{fund.denomination}</p>
                          <p className="text-xs text-muted-foreground truncate">{fund.manager}</p>
                        </div>
                        <StarButton active={isStarred(fund.fund)} onClick={() => toggleStar(fund.fund)} size={14} className="mt-0.5 shrink-0" />
                      </div>
                      {aum !== undefined && (
                        <p className="text-xs font-mono text-muted-foreground mt-1.5">
                          AUM {aum > 0 ? formatValue(aum) : "$0"}
                        </p>
                      )}
                    </div>
                  );
                })}
                {filtered.length === 0 && (
                  <p className="col-span-full text-center text-muted-foreground py-8">
                    No funds match your search.
                  </p>
                )}
              </div>
            </TabsContent>
            <TabsContent value="byvalue">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mt-4">
                {filtered.map((fund, i) => {
                  const aum = fundAumMap.get(fund.fund);
                  return (
                    <div
                      key={fund.cik}
                      className="kpi-card cursor-pointer"
                      onClick={() => navigate(`/funds/${encodeURIComponent(fund.fund)}`)}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold truncate">{fund.denomination}</p>
                          <p className="text-xs text-muted-foreground truncate">{fund.manager}</p>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <StarButton active={isStarred(fund.fund)} onClick={() => toggleStar(fund.fund)} size={14} className="mt-0.5" />
                          <span className="text-xs font-mono text-muted-foreground whitespace-nowrap">
                            #{i + 1}
                          </span>
                        </div>
                      </div>
                      {aum !== undefined && (
                        <p className="text-xs font-mono text-muted-foreground mt-1.5">
                          AUM {aum > 0 ? formatValue(aum) : "$0"}
                        </p>
                      )}
                    </div>
                  );
                })}
                {filtered.length === 0 && (
                  <p className="col-span-full text-center text-muted-foreground py-8">
                    No funds match your search.
                  </p>
                )}
              </div>
            </TabsContent>
          </>
        )}
      </Tabs>
    </div>
  );
}

// ────────────────────────── Helpers ──────────────────────────

function parseValue(v: string): number {
  if (!v || v === "N/A") return 0;
  const cleaned = v.replace(/[,$]/g, "");
  const match = cleaned.match(/^(-?[\d.]+)([BMK])?$/i);
  if (!match) return parseFloat(cleaned) || 0;
  const num = parseFloat(match[1]);
  const suffix = (match[2] || "").toUpperCase();
  if (suffix === "B") return num * 1_000_000_000;
  if (suffix === "M") return num * 1_000_000;
  if (suffix === "K") return num * 1_000;
  return num;
}

function formatValue(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

type SortKey = "portfolioPct" | "value" | "shares" | "deltaShares" | "delta";
type SortDir = "asc" | "desc";

// ────────────────────────── Fund Detail ──────────────────────────

function FundDetail({ fundName }: { fundName: string }) {
  const navigate = useNavigate();
  const [quarter, setQuarter] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("portfolioPct");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [showAll, setShowAll] = useState(false);
  const [positionFilter, setPositionFilter] = useState<"all" | "new" | "closed">("all");
  const TOP_N = 50;
  const { isStarred, toggle: toggleStar } = useStarred("fund");

  const { data: availableQuarters = [], isLoading: quartersLoading } = useQuery({
    queryKey: ["fundAvailableQuarters", fundName],
    queryFn: () => getFundAvailableQuarters(fundName),
  });

  // Auto-select latest available quarter
  const selectedQuarter = quarter && isQuarter(quarter) && availableQuarters.includes(quarter)
    ? quarter
    : availableQuarters[availableQuarters.length - 1] ?? null;

  const { data: fund } = useQuery({
    queryKey: ["hedgeFunds"],
    queryFn: getHedgeFunds,
    select: (funds) => funds.find((f) => f.fund === fundName),
  });

  const { data: stocksMaster = [] } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
  });
  const tickerNameMap = useMemo(() => new Map(stocksMaster.map((s) => [s.ticker, s.company])), [stocksMaster]);

  const { data: holdings = [], isLoading, isError } = useQuery({
    queryKey: ["fundHoldings", selectedQuarter, fundName],
    queryFn: () => getFundQuarterlyHoldings(selectedQuarter!, fundName),
    select: (data) => data.filter((h) => h.cusip !== "Total").map((h) => ({
      ...h,
      company: tickerNameMap.get(h.ticker) || h.company,
    })),
    enabled: !!selectedQuarter,
  });

  const sorted = useMemo(() => {
    let arr = [...holdings];
    if (positionFilter === "new") arr = arr.filter((h) => h.delta === "NEW");
    else if (positionFilter === "closed") arr = arr.filter((h) => h.delta === "CLOSE");
    arr.sort((a, b) => {
      let va: number, vb: number;
      switch (sortKey) {
        case "portfolioPct": va = a.portfolioPct; vb = b.portfolioPct; break;
        case "value": va = parseValue(a.value); vb = parseValue(b.value); break;
        case "shares": va = a.shares; vb = b.shares; break;
        case "deltaShares": va = a.deltaShares; vb = b.deltaShares; break;
        case "delta":
          va = a.delta === "NEW" ? 9999 : parseFloat(a.delta) || 0;
          vb = b.delta === "NEW" ? 9999 : parseFloat(b.delta) || 0;
          break;
        default: va = 0; vb = 0;
      }
      return sortDir === "desc" ? vb - va : va - vb;
    });
    return arr;
  }, [holdings, sortKey, sortDir, positionFilter]);

  const totalValue = useMemo(
    () => holdings.reduce((s, h) => s + parseValue(h.value), 0),
    [holdings]
  );

  const newPositions = useMemo(
    () => holdings.filter((h) => h.delta === "NEW").length,
    [holdings]
  );

  const closedPositions = useMemo(
    () => holdings.filter((h) => h.delta === "CLOSE").length,
    [holdings]
  );

  const treemapData = useMemo(() => {
    const byPct = [...holdings].filter((h) => h.delta !== "CLOSE").sort((a, b) => b.portfolioPct - a.portfolioPct);
    return byPct.slice(0, 20).map((h) => {
      const prevShares = h.shares - h.deltaShares;
      const deltaPct = prevShares > 0 && h.shares > 0 ? (h.deltaShares / prevShares) * 100 : 0;
      return {
        name: h.ticker,
        company: h.company,
        value: h.portfolioPct,
        deltaPct,
        delta: h.delta,
      };
    });
  }, [holdings]);


  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortKey(key); setSortDir("desc"); }
  }

  function sortIndicator(key: SortKey) {
    if (sortKey !== key) return null;
    return sortDir === "desc" ? " ↓" : " ↑";
  }

  const quarterLabel = selectedQuarter ? selectedQuarter.replace("Q", " Q") : "—";

  if (quartersLoading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading available quarters…
      </div>
    );
  }

  if (availableQuarters.length === 0) {
    return (
      <div className="space-y-5 max-w-7xl">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/funds")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Wallet className="h-6 w-6" /> {fund?.denomination || formatFundName(fundName)}
            <StarButton active={isStarred(fundName)} onClick={() => toggleStar(fundName)} size={20} />
          </h1>
        </div>
        <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
          No quarterly data available for this fund.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 max-w-7xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/funds")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <Wallet className="h-6 w-6" /> {fund?.denomination || formatFundName(fundName)}
              <StarButton active={isStarred(fundName)} onClick={() => toggleStar(fundName)} size={20} />
            </h1>
            {fund && (
              <p className="text-sm text-muted-foreground mt-0.5">
                Managed by {fund.manager}
              </p>
            )}
          </div>
        </div>
        <div className="flex gap-3">
          <Select value={selectedQuarter || ""} onValueChange={setQuarter}>
            <SelectTrigger className="w-36 bg-card border-border">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[...availableQuarters].reverse().map((q) => (
                <SelectItem key={q} value={q}>
                  {q.replace("Q", " Q")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid lg:grid-cols-4 gap-6">
        {/* Left: KPIs + Table */}
        <div className="lg:col-span-3 space-y-5">
          {/* Summary KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="kpi-card">
              <p className="text-xs text-muted-foreground">AUM</p>
              <p className="text-xl font-bold font-mono mt-1">{formatValue(totalValue)}</p>
            </div>
            <div className="kpi-card">
              <p className="text-xs text-muted-foreground">Positions</p>
              <p className="text-xl font-bold font-mono mt-1">{holdings.filter((h) => parseValue(h.value) > 0).length}</p>
            </div>
            <div
              className={`kpi-card cursor-pointer transition-colors ${positionFilter === "new" ? "ring-1 ring-primary" : "hover:bg-muted/50"}`}
              onClick={() => setPositionFilter((f) => f === "new" ? "all" : "new")}
            >
              <p className="text-xs text-muted-foreground flex items-center gap-1">New Positions <Filter className="h-3 w-3" /></p>
              <p className="text-xl font-bold font-mono mt-1 delta-positive">{newPositions}</p>
            </div>
            <div
              className={`kpi-card cursor-pointer transition-colors ${positionFilter === "closed" ? "ring-1 ring-primary" : "hover:bg-muted/50"}`}
              onClick={() => setPositionFilter((f) => f === "closed" ? "all" : "closed")}
            >
              <p className="text-xs text-muted-foreground flex items-center gap-1">Closed Positions <Filter className="h-3 w-3" /></p>
              <p className="text-xl font-bold font-mono mt-1 delta-negative">{closedPositions}</p>
            </div>
          </div>

          {isLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
              <Loader2 className="h-5 w-5 animate-spin" /> Loading holdings for {quarterLabel}…
            </div>
          ) : isError ? (
            <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
              No data available for {fundName} in {quarterLabel}. Try a different quarter.
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-xs text-muted-foreground uppercase tracking-wider">
                      <th className="text-left p-3 font-medium">#</th>
                      <th className="text-left p-3 font-medium">Ticker</th>
                      <th className="text-left p-3 font-medium">Company</th>
                      <th className="text-right p-3 font-medium">Value</th>
                      <th
                        className="text-right p-3 font-medium cursor-pointer hover:text-foreground"
                        onClick={() => toggleSort("delta")}
                      >
                        Δ%{sortIndicator("delta")}
                      </th>
                      <th
                        className="text-right p-3 font-medium cursor-pointer hover:text-foreground"
                        onClick={() => toggleSort("portfolioPct")}
                      >
                        Port %{sortIndicator("portfolioPct")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {(showAll ? sorted : sorted.slice(0, TOP_N)).map((h, i) => {
                      const isNew = h.delta === "NEW";
                      const isClosed = h.delta === "CLOSE";
                      const deltaParsed = isNew || isClosed ? 0 : parseFloat(h.delta) || 0;
                      return (
                        <tr key={`${h.cusip}-${i}`} className="data-table-row">
                          <td className="p-3 text-muted-foreground font-mono">{i + 1}</td>
                          <td className="p-3">
                            <TickerLink ticker={h.ticker} />
                          </td>
                          <td className="p-3 text-muted-foreground max-w-[200px] truncate cursor-pointer hover:text-foreground transition-colors" onClick={() => navigate(`/stock/${h.ticker}`)}>
                            {toInitCap(h.company)}
                          </td>
                          <td className="p-3 text-right font-mono">{h.value}</td>
                          <td className="p-3 text-right font-mono">
                            {isNew ? (
                              <span className="badge-new">NEW</span>
                            ) : isClosed ? (
                              <span className="badge-closed">CLOSE</span>
                            ) : deltaParsed === 0 ? (
                              <span className="badge-nochange">NO CHANGE</span>
                            ) : (
                              <span className={deltaParsed > 0 ? "delta-positive" : "delta-negative"}>
                                {`${deltaParsed > 0 ? "+" : ""}${deltaParsed.toFixed(2)}%`}
                              </span>
                            )}
                          </td>
                          <td className="p-3 text-right font-mono">
                            {h.portfolioPct.toFixed(1)}%
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  {!showAll && sorted.length > TOP_N && (
                    <tfoot>
                      <tr>
                        <td colSpan={6} className="p-3 text-center">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-xs text-muted-foreground hover:text-foreground"
                            onClick={() => setShowAll(true)}
                          >
                            Showing top {TOP_N} of {sorted.length} positions — Show all
                          </Button>
                        </td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Right: Holdings Map - full height */}
        <div className="lg:sticky lg:top-4 lg:self-start rounded-lg border border-border bg-card p-5">
          <h3 className="section-title mb-3 text-sm">Holdings Map</h3>
          <HoldingsTreemap data={treemapData} onClickTicker={(t) => navigate(`/stock/${t}`)} displayMode="pct" />
        </div>
      </div>
    </div>
  );
}

// ────────────────────────── Main Component ──────────────────────────

export default function FundPortfolio() {
  const { fundId } = useParams();
  if (fundId) return <FundDetail fundName={decodeURIComponent(fundId)} />;
  return <FundGrid />;
}
