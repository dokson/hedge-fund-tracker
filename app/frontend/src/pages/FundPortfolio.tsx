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
  aggregateHoldingsByTicker,
} from "@/lib/dataService";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { TickerLink, CompanyLink, formatFundName } from "@/components/EntityLinks";
import { FundLogo } from "@/components/FundLogo";
import { Delta } from "@/components/Delta";
import { toInitCap } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { HoldingsTreemap } from "@/components/HoldingsTreemap";

import {
  Search,
  ArrowLeft,
  Loader2,
  Wallet,
  Filter,
  SortAsc,
  DollarSign,
  Star,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useStarred } from "@/hooks/useStarred";
import { StarButton } from "@/components/StarButton";

// ────────────────────────── Fund Grid ──────────────────────────

function FundGrid() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const { starred, toggle: toggleStar, isStarred } = useStarred("fund");
  const [tab, setTab] = useState<"starred" | "alphabetical" | "byvalue">(() =>
    starred.size > 0 ? "starred" : "alphabetical",
  );

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
          } catch {
            /* skip */
          }
        }),
      );
      return aumMap;
    },
    enabled: funds.length > 0,
  });

  const starredFunds = useMemo(() => {
    return funds
      .filter((f) => starred.has(f.fund))
      .sort((a, b) => a.denomination.localeCompare(b.denomination));
  }, [funds, starred]);

  const filtered = useMemo(() => {
    let list = funds;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (f) =>
          f.fund.toLowerCase().includes(q) ||
          f.manager.toLowerCase().includes(q) ||
          f.denomination.toLowerCase().includes(q),
      );
    }
    if (tab === "byvalue") {
      list = [...list].sort(
        (a, b) => (fundAumMap.get(b.fund) || 0) - (fundAumMap.get(a.fund) || 0),
      );
    } else {
      list = [...list].sort((a, b) => a.denomination.localeCompare(b.denomination));
    }
    return list;
  }, [funds, search, tab, fundAumMap]);

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div>
        <span className="eyebrow">Tracked funds</span>
        <h1 className="page-title mt-1.5">
          <Wallet className="page-title-icon" /> Hedge Fund Portfolios
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Browse {funds.length} tracked institutional investors
        </p>
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
        <div className="flex flex-wrap items-center gap-3">
          <TabsList>
            {starred.size > 0 && (
              <TabsTrigger value="starred" className="gap-1.5 group">
                <Star className="h-3.5 w-3.5" fill="currentColor" /> Starred
                <span className="ml-1 text-[10px] font-mono bg-primary/20 text-primary group-data-[state=active]:bg-primary-foreground/20 group-data-[state=active]:text-primary-foreground px-1.5 py-0.5 rounded-full leading-none">
                  {starred.size}
                </span>
              </TabsTrigger>
            )}
            <TabsTrigger value="alphabetical" className="gap-1.5">
              <SortAsc className="h-3.5 w-3.5" /> Alphabetical
            </TabsTrigger>
            <TabsTrigger value="byvalue" className="gap-1.5">
              <DollarSign className="h-3.5 w-3.5" /> AUM
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
            <div className="surface p-12 text-center mt-4">
              <Star className="h-8 w-8 mx-auto text-muted-foreground/30 mb-3" />
              <p className="text-muted-foreground">No starred funds yet.</p>
              <p className="text-xs text-muted-foreground/60 mt-1">
                Click the ★ icon on any fund to add it here.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mt-4">
              {starredFunds.map((fund) => {
                const aum = fundAumMap.get(fund.fund);
                return (
                  <div
                    key={fund.cik}
                    role="button"
                    tabIndex={0}
                    className="kpi-card cursor-pointer"
                    onClick={() => navigate(`/funds/${encodeURIComponent(fund.fund)}`)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        navigate(`/funds/${encodeURIComponent(fund.fund)}`);
                      }
                    }}
                  >
                    <div className="flex items-start gap-3">
                      <div className="rounded-md border border-border bg-neutral-200 p-1 shrink-0">
                        <FundLogo
                          fundName={fund.fund}
                          url={fund.url}
                          size={28}
                          className="rounded-md"
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold truncate">{fund.denomination}</p>
                            <p className="text-xs text-muted-foreground truncate">{fund.manager}</p>
                          </div>
                          <StarButton
                            active={true}
                            onClick={() => toggleStar(fund.fund)}
                            size={14}
                            className="mt-0.5 shrink-0"
                          />
                        </div>
                        {aum !== undefined && (
                          <p className="text-xs font-mono text-muted-foreground mt-1.5">
                            AUM {aum > 0 ? formatValue(aum) : "$0"}
                          </p>
                        )}
                      </div>
                    </div>
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
                      role="button"
                      tabIndex={0}
                      className="kpi-card cursor-pointer"
                      onClick={() => navigate(`/funds/${encodeURIComponent(fund.fund)}`)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          navigate(`/funds/${encodeURIComponent(fund.fund)}`);
                        }
                      }}
                    >
                      <div className="flex items-start gap-3">
                        <div className="rounded-md border border-border bg-neutral-200 p-1 shrink-0">
                          <FundLogo
                            fundName={fund.fund}
                            url={fund.url}
                            size={28}
                            className="rounded-md"
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="text-sm font-semibold truncate">{fund.denomination}</p>
                              <p className="text-xs text-muted-foreground truncate">
                                {fund.manager}
                              </p>
                            </div>
                            <StarButton
                              active={isStarred(fund.fund)}
                              onClick={() => toggleStar(fund.fund)}
                              size={14}
                              className="mt-0.5 shrink-0"
                            />
                          </div>
                          {aum !== undefined && (
                            <p className="text-xs font-mono text-muted-foreground mt-1.5">
                              AUM {aum > 0 ? formatValue(aum) : "$0"}
                            </p>
                          )}
                        </div>
                      </div>
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
                      role="button"
                      tabIndex={0}
                      className="kpi-card cursor-pointer"
                      onClick={() => navigate(`/funds/${encodeURIComponent(fund.fund)}`)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          navigate(`/funds/${encodeURIComponent(fund.fund)}`);
                        }
                      }}
                    >
                      <div className="flex items-start gap-3">
                        <div className="rounded-md border border-border bg-neutral-200 p-1 shrink-0">
                          <FundLogo
                            fundName={fund.fund}
                            url={fund.url}
                            size={28}
                            className="rounded-md"
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="text-sm font-semibold truncate">{fund.denomination}</p>
                              <p className="text-xs text-muted-foreground truncate">
                                {fund.manager}
                              </p>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <StarButton
                                active={isStarred(fund.fund)}
                                onClick={() => toggleStar(fund.fund)}
                                size={14}
                                className="mt-0.5"
                              />
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
                      </div>
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

/**
 * Renders the Δ cell for a single holding row. Top-level component instead of
 * an inline IIFE so it can be optimised by React Compiler.
 */
function HoldingDeltaCell({
  isNew,
  isClosed,
  deltaPct,
  deltaValueRaw,
}: {
  isNew: boolean;
  isClosed: boolean;
  deltaPct: number;
  deltaValueRaw: string;
}) {
  const deltaValueNum = parseValueString(deltaValueRaw);
  const deltaValue =
    deltaValueNum !== 0 ? (
      <div className="mt-0.5 opacity-70 flex justify-end">
        <Delta value={deltaValueNum} mode="currency" size="sm" />
      </div>
    ) : null;

  if (isNew) {
    return (
      <>
        <span className="badge-new">NEW</span>
        {deltaValue}
      </>
    );
  }
  if (isClosed) {
    return (
      <>
        <span className="badge-closed">CLOSE</span>
        {deltaValue}
      </>
    );
  }
  if (deltaPct === 0) {
    return <span className="badge-nochange">NO CHANGE</span>;
  }
  return (
    <div className="flex flex-col items-end gap-0.5">
      <Delta value={deltaPct} mode="percent" />
      {deltaValue}
    </div>
  );
}

function FundDetail({ fundName }: { fundName: string }) {
  const navigate = useNavigate();
  const [quarter, setQuarter] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("portfolioPct");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [showAll, setShowAll] = useState(false);
  const [positionFilter, setPositionFilter] = useState<
    "all" | "new" | "closed" | "increased" | "decreased"
  >("all");
  const [sectorFilter, setSectorFilter] = useState<string>("all");
  const TOP_N = 50;
  const { isStarred, toggle: toggleStar } = useStarred("fund");

  const { data: availableQuarters = [], isLoading: quartersLoading } = useQuery({
    queryKey: ["fundAvailableQuarters", fundName],
    queryFn: () => getFundAvailableQuarters(fundName),
  });

  // Auto-select latest available quarter
  const selectedQuarter =
    quarter && isQuarter(quarter) && availableQuarters.includes(quarter)
      ? quarter
      : (availableQuarters[availableQuarters.length - 1] ?? null);

  const { data: fund } = useQuery({
    queryKey: ["hedgeFunds"],
    queryFn: getHedgeFunds,
    select: (funds) => funds.find((f) => f.fund === fundName),
  });

  const { data: stocksMaster = [] } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
  });
  const tickerNameMap = useMemo(
    () => new Map(stocksMaster.map((s) => [s.ticker, s.company])),
    [stocksMaster],
  );
  const tickerSectorMap = useMemo(
    () => new Map(stocksMaster.map((s) => [s.ticker, s.sector ?? "Unclassified"])),
    [stocksMaster],
  );

  const {
    data: holdings = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["fundHoldings", selectedQuarter, fundName],
    queryFn: () => getFundQuarterlyHoldings(selectedQuarter!, fundName),
    // Collapse multiple CUSIPs of the same ticker (e.g. common stock + a
    // 13F-reportable note) into a single row, matching the stock page, the
    // consensus view and the CLI fund analysis.
    select: (data) =>
      aggregateHoldingsByTicker(
        data.map((h) => ({
          ...h,
          company: tickerNameMap.get(h.ticker) || h.company,
        })),
      ),
    enabled: !!selectedQuarter,
  });

  const fundSectors = useMemo(() => {
    const set = new Set<string>();
    for (const h of holdings) {
      if (h.delta === "CLOSE" || h.portfolioPct <= 0) continue;
      set.add(tickerSectorMap.get(h.ticker) ?? "Unclassified");
    }
    return [...set].sort();
  }, [holdings, tickerSectorMap]);

  // Guard against a sector that no longer exists in the selected quarter.
  const activeSector =
    sectorFilter !== "all" && fundSectors.includes(sectorFilter) ? sectorFilter : "all";

  const sorted = useMemo(() => {
    let arr = [...holdings];
    if (positionFilter === "new") arr = arr.filter((h) => h.delta === "NEW");
    else if (positionFilter === "closed") arr = arr.filter((h) => h.delta === "CLOSE");
    else if (positionFilter === "increased")
      arr = arr.filter((h) => h.delta !== "NEW" && h.delta !== "CLOSE" && h.deltaShares > 0);
    else if (positionFilter === "decreased")
      arr = arr.filter((h) => h.delta !== "CLOSE" && h.deltaShares < 0);
    if (activeSector !== "all")
      arr = arr.filter((h) => (tickerSectorMap.get(h.ticker) ?? "Unclassified") === activeSector);
    arr.sort((a, b) => {
      let va: number, vb: number;
      switch (sortKey) {
        case "portfolioPct":
          va = a.portfolioPct;
          vb = b.portfolioPct;
          break;
        case "value":
          va = parseValue(a.value);
          vb = parseValue(b.value);
          break;
        case "shares":
          va = a.shares;
          vb = b.shares;
          break;
        case "deltaShares":
          va = a.deltaShares;
          vb = b.deltaShares;
          break;
        case "delta":
          va = a.delta === "NEW" ? 9999 : parseFloat(a.delta) || 0;
          vb = b.delta === "NEW" ? 9999 : parseFloat(b.delta) || 0;
          break;
        default:
          va = 0;
          vb = 0;
      }
      return sortDir === "desc" ? vb - va : va - vb;
    });
    return arr;
  }, [holdings, sortKey, sortDir, positionFilter, activeSector, tickerSectorMap]);

  const totalValue = useMemo(
    () => holdings.reduce((s, h) => s + parseValue(h.value), 0),
    [holdings],
  );

  const newPositions = useMemo(() => holdings.filter((h) => h.delta === "NEW").length, [holdings]);

  const closedPositions = useMemo(
    () => holdings.filter((h) => h.delta === "CLOSE").length,
    [holdings],
  );

  const increasedPositions = useMemo(
    () =>
      holdings.filter((h) => h.delta !== "NEW" && h.delta !== "CLOSE" && h.deltaShares > 0).length,
    [holdings],
  );
  const decreasedPositions = useMemo(
    () => holdings.filter((h) => h.delta !== "CLOSE" && h.deltaShares < 0).length,
    [holdings],
  );
  const treemapData = useMemo(() => {
    const byPct = [...holdings]
      .filter((h) => h.delta !== "CLOSE")
      .sort((a, b) => b.portfolioPct - a.portfolioPct);
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

  // Sector-level treemap: aggregate the fund's current positions by Yahoo
  // Finance sector (joined via stocks.csv → sector_hierarchy.csv inside
  // getStocks). Δ is a value-weighted average across the holdings in each
  // sector so the colour reflects net institutional behaviour at the sector
  // level, not just the largest single position.
  const sectorTreemapData = useMemo(() => {
    const buckets = new Map<string, { value: number; weightedDelta: number }>();
    for (const h of holdings) {
      if (h.delta === "CLOSE" || h.portfolioPct <= 0) continue;
      const sector = tickerSectorMap.get(h.ticker) ?? "Unclassified";
      const prevShares = h.shares - h.deltaShares;
      const deltaPct = prevShares > 0 && h.shares > 0 ? (h.deltaShares / prevShares) * 100 : 0;
      const acc = buckets.get(sector) ?? { value: 0, weightedDelta: 0 };
      acc.value += h.portfolioPct;
      acc.weightedDelta += deltaPct * h.portfolioPct;
      buckets.set(sector, acc);
    }
    return [...buckets.entries()]
      .map(([sector, agg]) => ({
        name: sector,
        company: sector,
        value: agg.value,
        deltaPct: agg.value > 0 ? agg.weightedDelta / agg.value : 0,
        delta: "",
      }))
      .sort((a, b) => b.value - a.value);
  }, [holdings, tickerSectorMap]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else {
      setSortKey(key);
      setSortDir("desc");
    }
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
      <div className="space-y-6 max-w-screen-2xl">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/funds")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="rounded-lg border border-border bg-neutral-200 p-2 shadow-sm ring-1 ring-border/50 shrink-0">
            <FundLogo fundName={fundName} url={fund?.url} size={28} className="rounded-md" />
          </div>
          <h1 className="page-title">
            {fund?.denomination || formatFundName(fundName)}
            <StarButton
              active={isStarred(fundName)}
              onClick={() => toggleStar(fundName)}
              size={20}
            />
          </h1>
        </div>
        <div className="surface p-8 text-center text-muted-foreground">
          No quarterly data available for this fund.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/funds")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="rounded-lg border border-border bg-neutral-200 p-2 shadow-sm ring-1 ring-border/50 shrink-0">
            <FundLogo fundName={fundName} url={fund?.url} size={28} className="rounded-md" />
          </div>
          <div>
            <h1 className="page-title">
              {fund?.denomination || formatFundName(fundName)}
              <StarButton
                active={isStarred(fundName)}
                onClick={() => toggleStar(fundName)}
                size={20}
              />
            </h1>
            {fund && (
              <p className="text-sm text-muted-foreground mt-0.5">Managed by {fund.manager}</p>
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
          {fundSectors.length > 1 && (
            <Select value={activeSector} onValueChange={setSectorFilter}>
              <SelectTrigger className="w-44 bg-card border-border">
                <SelectValue placeholder="All sectors" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All sectors</SelectItem>
                {fundSectors.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      </div>

      <div className="grid lg:grid-cols-5 gap-6">
        {/* Left: KPIs + Table */}
        <div className="lg:col-span-3 space-y-5">
          {/* Summary KPIs — 6 compact cells: 2 static + 4 toggle filters */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <div className="surface flex flex-col gap-1 p-3">
              <p className="metric-label">AUM</p>
              <p className="font-mono text-lg font-bold leading-tight">{formatValue(totalValue)}</p>
            </div>
            <div className="surface flex flex-col gap-1 p-3">
              <p className="metric-label">Positions</p>
              <p className="font-mono text-lg font-bold leading-tight">
                {holdings.filter((h) => parseValue(h.value) > 0).length}
              </p>
            </div>
            {(
              [
                {
                  key: "new",
                  label: "New",
                  count: newPositions,
                  num: "text-primary",
                  ring: "ring-primary/50",
                },
                {
                  key: "closed",
                  label: "Closed",
                  count: closedPositions,
                  num: "text-closed",
                  ring: "ring-closed/50",
                },
                {
                  key: "increased",
                  label: "Increased",
                  count: increasedPositions,
                  num: "text-positive",
                  ring: "ring-positive/50",
                },
                {
                  key: "decreased",
                  label: "Decreased",
                  count: decreasedPositions,
                  num: "text-negative",
                  ring: "ring-negative/50",
                },
              ] as const
            ).map((f) => {
              const active = positionFilter === f.key;
              return (
                <button
                  key={f.key}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setPositionFilter((cur) => (cur === f.key ? "all" : f.key))}
                  className={`surface flex flex-col gap-1 p-3 text-left transition-colors ${active ? `ring-1 ${f.ring}` : "hover:border-border"}`}
                >
                  <p className="metric-label flex items-center gap-1">
                    {f.label} <Filter className="h-2.5 w-2.5 opacity-50" />
                  </p>
                  <p className={`font-mono text-lg font-bold leading-tight ${f.num}`}>{f.count}</p>
                </button>
              );
            })}
          </div>

          {isLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
              <Loader2 className="h-5 w-5 animate-spin" /> Loading holdings for {quarterLabel}…
            </div>
          ) : isError ? (
            <div className="surface p-8 text-center text-muted-foreground">
              No data available for {fundName} in {quarterLabel}. Try a different quarter.
            </div>
          ) : (
            <div className="surface overflow-hidden">
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
                        Δ{sortIndicator("delta")}
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
                        <tr key={`${h.cusip}-${h.ticker}-${h.delta}`} className="data-table-row">
                          <td className="p-3 text-muted-foreground font-mono">{i + 1}</td>
                          <td className="p-3">
                            <TickerLink ticker={h.ticker} />
                          </td>
                          <td className="p-3">
                            <CompanyLink
                              ticker={h.ticker}
                              company={toInitCap(h.company)}
                              className="max-w-[180px] xl:max-w-[260px]"
                              showStar
                            />
                          </td>
                          <td className="p-3 text-right font-mono">{h.value}</td>
                          <td className="p-3 text-right font-mono">
                            <HoldingDeltaCell
                              isNew={isNew}
                              isClosed={isClosed}
                              deltaPct={deltaParsed}
                              deltaValueRaw={h.deltaValue}
                            />
                          </td>
                          <td className="p-3 text-right font-mono">{h.portfolioPct.toFixed(1)}%</td>
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

        {/* Right: Holdings Map + Sector Map side-by-side (stack on narrow viewports) */}
        <div className="lg:col-span-2 lg:sticky lg:top-4 lg:self-start grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="surface p-5">
            <h3 className="section-title mb-3 text-sm">Holdings Map</h3>
            <HoldingsTreemap
              data={treemapData}
              onClickTicker={(t) => navigate(`/stock/${t}`)}
              displayMode="pct"
            />
          </div>
          {sectorTreemapData.length > 0 && (
            <div className="surface p-5">
              <h3 className="section-title mb-3 text-sm">Sector Map</h3>
              <HoldingsTreemap
                data={sectorTreemapData}
                onClickTicker={(sector) =>
                  setSectorFilter((cur) => (cur === sector ? "all" : sector))
                }
                displayMode="pct"
              />
            </div>
          )}
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
