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
  formatValue,
  aggregateHoldingsByTicker,
  getNonQuarterlyFilings,
  type HedgeFund,
  type QuarterlyHolding,
} from "@/lib/dataService";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { TickerLink, CompanyLink, formatFundName } from "@/components/EntityLinks";
import { FundLogo } from "@/components/FundLogo";
import { Delta } from "@/components/Delta";
import { toInitCap, matchesQuery } from "@/lib/utils";
import { fundPath, stockPath, ROUTES } from "@/lib/routes";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SearchInput } from "@/components/ui/SearchInput";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { HoldingsTreemap } from "@/components/HoldingsTreemap";

import { ArrowLeft, Clock, Wallet, Filter, SortAsc, DollarSign, Star, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useStarred } from "@/hooks/useStarred";
import { StarButton } from "@/components/StarButton";

// ────────────────────────── Fund Grid ──────────────────────────

interface FundMeta {
  aum: number;
  latestQuarter: string | null;
}

/**
 * One clickable fund tile, shared by every FundGrid tab: logo, names, star,
 * optional AUM rank, AUM line and the latest-quarter chip (highlighted when
 * the fund has already filed the most recent quarter).
 */
function FundCard({
  fund,
  meta,
  overallLatestQuarter,
  rank,
  starred,
  onToggleStar,
  onOpen,
}: {
  fund: HedgeFund;
  meta: FundMeta | undefined;
  overallLatestQuarter: string | null;
  rank?: number;
  starred: boolean;
  onToggleStar: () => void;
  onOpen: () => void;
}) {
  const latestQuarter = meta?.latestQuarter ?? null;
  const isCurrent = latestQuarter !== null && latestQuarter === overallLatestQuarter;
  return (
    <div
      role="button"
      tabIndex={0}
      className="kpi-card cursor-pointer"
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
    >
      <div className="flex items-start gap-3">
        <div className="rounded-md border border-border bg-neutral-200 p-1 shrink-0">
          <FundLogo fundName={fund.fund} url={fund.url} size={28} className="rounded-md" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-sm font-semibold truncate">{fund.denomination}</p>
              <p className="text-xs text-muted-foreground truncate">{fund.manager}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <StarButton active={starred} onClick={onToggleStar} size={14} className="mt-0.5" />
              {rank !== undefined && (
                <span className="text-xs font-mono text-muted-foreground whitespace-nowrap">
                  #{rank}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center justify-between gap-2 mt-1.5">
            {meta !== undefined && (
              <p className="text-xs font-mono text-muted-foreground">
                AUM {meta.aum > 0 ? formatValue(meta.aum) : "$0"}
              </p>
            )}
            {latestQuarter && (
              <span
                className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-mono font-medium ${
                  isCurrent
                    ? "border-[hsl(var(--positive))]/40 bg-[hsl(var(--positive))]/10 text-[hsl(var(--positive))]"
                    : "border-border text-muted-foreground"
                }`}
                title={
                  isCurrent
                    ? "This fund has already filed the most recent quarter"
                    : "Latest quarter this fund has filed"
                }
              >
                <Clock className="h-2.5 w-2.5" aria-hidden="true" />
                {latestQuarter.replace("Q", " Q")}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function FundGrid() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const { starred, toggle: toggleStar, isStarred } = useStarred("fund");
  const [tab, setTab] = useState<"starred" | "updated" | "alphabetical" | "byvalue">(() =>
    starred.size > 0 ? "starred" : "updated",
  );

  const { data: funds = [], isLoading } = useQuery({
    queryKey: ["hedgeFunds"],
    queryFn: getHedgeFunds,
  });
  const { latestQuarter: overallLatestQuarter } = useAvailableQuarters();

  // Load AUM + latest filed quarter for each fund (single sweep, cached).
  const { data: fundMetaMap = new Map<string, FundMeta>() } = useQuery({
    queryKey: ["fundMetaMap", funds.length],
    queryFn: async () => {
      const metaMap = new Map<string, FundMeta>();
      await Promise.all(
        funds.map(async (fund) => {
          try {
            const quarters = await getFundAvailableQuarters(fund.fund);
            if (quarters.length === 0) return;
            const latest = quarters[quarters.length - 1];
            const holdings = await getFundQuarterlyHoldings(latest, fund.fund);
            const total = holdings
              .filter((h) => h.cusip !== "Total")
              .reduce((sum, h) => sum + parseValueString(h.value), 0);
            metaMap.set(fund.fund, { aum: total, latestQuarter: latest });
          } catch {
            /* skip */
          }
        }),
      );
      return metaMap;
    },
    enabled: funds.length > 0,
  });

  // Latest non-quarterly filing date per fund: day-level tiebreaker for the
  // Last Updated ordering (a 13D/G or Form 4 is fresher evidence than a 13F).
  const { data: nqLatestByFund = new Map<string, string>() } = useQuery({
    queryKey: ["nqLatestByFund"],
    queryFn: async () => {
      const filings = await getNonQuarterlyFilings();
      const map = new Map<string, string>();
      for (const f of filings) {
        const current = map.get(f.fund);
        if (!current || f.filingDate > current) map.set(f.fund, f.filingDate);
      }
      return map;
    },
    staleTime: 10 * 60 * 1000,
  });

  const starredFunds = useMemo(() => {
    return funds
      .filter((f) => starred.has(f.fund))
      .sort((a, b) => a.denomination.localeCompare(b.denomination));
  }, [funds, starred]);

  const filtered = useMemo(() => {
    // Primary key: the latest filed quarter (what the card's chip shows), so
    // every current-quarter filer leads. Non-quarterly recency only breaks
    // ties within the same quarter.
    const lastUpdatedOf = (fund: HedgeFund): string => {
      const quarter = fundMetaMap.get(fund.fund)?.latestQuarter ?? "";
      const nq = nqLatestByFund.get(fund.fund) ?? "";
      return quarter + "|" + nq;
    };
    let list = funds;
    if (search) {
      list = list.filter((f) => matchesQuery(search, f.fund, f.manager, f.denomination));
    }
    if (tab === "byvalue") {
      list = [...list].sort(
        (a, b) => (fundMetaMap.get(b.fund)?.aum || 0) - (fundMetaMap.get(a.fund)?.aum || 0),
      );
    } else if (tab === "updated") {
      list = [...list].sort(
        (a, b) =>
          lastUpdatedOf(b).localeCompare(lastUpdatedOf(a)) ||
          a.denomination.localeCompare(b.denomination),
      );
    } else {
      list = [...list].sort((a, b) => a.denomination.localeCompare(b.denomination));
    }
    return list;
  }, [funds, search, tab, fundMetaMap, nqLatestByFund]);

  const renderCards = (list: HedgeFund[], withRank = false) => (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mt-4">
      {list.map((fund, i) => (
        <FundCard
          key={fund.cik}
          fund={fund}
          meta={fundMetaMap.get(fund.fund)}
          overallLatestQuarter={overallLatestQuarter ?? null}
          rank={withRank ? i + 1 : undefined}
          starred={isStarred(fund.fund)}
          onToggleStar={() => toggleStar(fund.fund)}
          onOpen={() => navigate(fundPath(fund.fund))}
        />
      ))}
      {list.length === 0 && (
        <p className="col-span-full text-center text-muted-foreground py-8">
          No funds match your search.
        </p>
      )}
    </div>
  );

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
            <TabsTrigger value="updated" className="gap-1.5">
              <Clock className="h-3.5 w-3.5" /> Last Updated
            </TabsTrigger>
            <TabsTrigger value="alphabetical" className="gap-1.5">
              <SortAsc className="h-3.5 w-3.5" /> Alphabetical
            </TabsTrigger>
            <TabsTrigger value="byvalue" className="gap-1.5">
              <DollarSign className="h-3.5 w-3.5" /> AUM
            </TabsTrigger>
          </TabsList>
          <SearchInput
            label="Search fund or manager"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            wrapperClassName="w-full sm:w-72"
          />
        </div>

        {/* Starred tab */}
        <TabsContent value="starred">
          {starredFunds.length === 0 ? (
            <EmptyState
              className="mt-4"
              icon={Star}
              title="No starred funds yet."
              description="Click the ★ icon on any fund to add it here."
            />
          ) : (
            renderCards(starredFunds)
          )}
        </TabsContent>

        {isLoading ? (
          <LoadingState message="Loading funds…" />
        ) : (
          <>
            <TabsContent value="updated">{renderCards(filtered)}</TabsContent>
            <TabsContent value="alphabetical">{renderCards(filtered)}</TabsContent>
            <TabsContent value="byvalue">{renderCards(filtered, true)}</TabsContent>
          </>
        )}
      </Tabs>
    </div>
  );
}

// ────────────────────────── Helpers ──────────────────────────

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

/**
 * Mobile card for a single holding row. The desktop holdings table is hidden
 * below `md` and replaced by a stack of these: ticker + portfolio weight on the
 * headline, company beneath, value and Δ as a two-up footer.
 */
function HoldingCard({ h, rank }: { h: QuarterlyHolding; rank: number }) {
  const isNew = h.delta === "NEW";
  const isClosed = h.delta === "CLOSE";
  const deltaParsed = isNew || isClosed ? 0 : parseFloat(h.delta) || 0;
  return (
    <div className="surface p-3.5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-mono text-xs text-muted-foreground shrink-0">#{rank}</span>
          <TickerLink ticker={h.ticker} />
        </div>
        <span className="font-mono text-sm font-semibold shrink-0">
          {h.portfolioPct.toFixed(1)}%
        </span>
      </div>
      <div className="mt-2">
        <CompanyLink ticker={h.ticker} company={toInitCap(h.company)} showStar />
      </div>
      <div className="mt-3 pt-3 border-t border-border/60 flex items-end justify-between gap-3">
        <div>
          <div className="metric-label">Value</div>
          <div className="font-mono text-sm text-foreground mt-0.5">{h.value}</div>
        </div>
        <div className="text-right">
          <div className="metric-label">Δ</div>
          <div className="font-mono mt-0.5">
            <HoldingDeltaCell
              isNew={isNew}
              isClosed={isClosed}
              deltaPct={deltaParsed}
              deltaValueRaw={h.deltaValue}
            />
          </div>
        </div>
      </div>
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
          va = parseValueString(a.value);
          vb = parseValueString(b.value);
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
    () => holdings.reduce((s, h) => s + parseValueString(h.value), 0),
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
  // Holdings Map mirrors the active sector filter so it stays coherent with the
  // central list and the Sector Map selection.
  const treemapData = useMemo(() => {
    const byPct = [...holdings]
      .filter((h) => h.delta !== "CLOSE")
      .filter(
        (h) =>
          activeSector === "all" ||
          (tickerSectorMap.get(h.ticker) ?? "Unclassified") === activeSector,
      )
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
  }, [holdings, activeSector, tickerSectorMap]);

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

  // Holdings in the active sector (held positions), for the filter chip count.
  const activeSectorCount = useMemo(() => {
    if (activeSector === "all") return 0;
    return holdings.filter(
      (h) =>
        h.delta !== "CLOSE" && (tickerSectorMap.get(h.ticker) ?? "Unclassified") === activeSector,
    ).length;
  }, [holdings, activeSector, tickerSectorMap]);

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
    return <LoadingState message="Loading available quarters…" />;
  }

  if (availableQuarters.length === 0) {
    return (
      <div className="space-y-6 max-w-screen-2xl">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate(ROUTES.funds)}>
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
          <Button variant="ghost" size="icon" onClick={() => navigate(ROUTES.funds)}>
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
        <div className="flex gap-3 w-full sm:w-auto">
          <Select value={selectedQuarter || ""} onValueChange={setQuarter}>
            <SelectTrigger className="flex-1 sm:flex-none sm:w-36 bg-card border-border">
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
                {holdings.filter((h) => parseValueString(h.value) > 0).length}
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

          {/* Active sector filter chip — mirrors the Stocks page pattern. */}
          {activeSector !== "all" && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-muted-foreground">Filtered by sector:</span>
              <button
                type="button"
                onClick={() => setSectorFilter("all")}
                className="inline-flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/10 text-primary px-2.5 py-0.5 text-xs font-medium hover:bg-primary/15 transition-colors"
              >
                {activeSector}
                <X className="h-3 w-3" aria-label="Clear sector filter" />
              </button>
              <span className="text-xs text-muted-foreground">
                · {activeSectorCount} holding{activeSectorCount === 1 ? "" : "s"}
              </span>
            </div>
          )}

          {isLoading ? (
            <LoadingState message={`Loading holdings for ${quarterLabel}…`} />
          ) : isError ? (
            <EmptyState
              padding="sm"
              title={`No data available for ${fundName} in ${quarterLabel}. Try a different quarter.`}
            />
          ) : (
            <>
              {/* Mobile: sort chips + card list */}
              <div className="md:hidden space-y-3">
                <div className="flex items-center gap-2 overflow-x-auto">
                  <span className="text-xs text-muted-foreground shrink-0">Sort</span>
                  {(
                    [
                      ["portfolioPct", "Port %"],
                      ["delta", "Δ"],
                    ] as const
                  ).map(([key, label]) => {
                    const active = sortKey === key;
                    return (
                      <button
                        key={key}
                        onClick={() => toggleSort(key)}
                        aria-pressed={active}
                        className={`inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors shrink-0 ${
                          active
                            ? "border-primary/50 bg-primary/10 text-primary"
                            : "border-border bg-card text-muted-foreground"
                        }`}
                      >
                        {label}
                        {active && (sortDir === "desc" ? " ↓" : " ↑")}
                      </button>
                    );
                  })}
                </div>
                {(showAll ? sorted : sorted.slice(0, TOP_N)).map((h, i) => (
                  <HoldingCard key={`${h.cusip}-${h.ticker}-${h.delta}`} h={h} rank={i + 1} />
                ))}
                {!showAll && sorted.length > TOP_N && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full text-xs text-muted-foreground hover:text-foreground"
                    onClick={() => setShowAll(true)}
                  >
                    Showing top {TOP_N} of {sorted.length} positions — Show all
                  </Button>
                )}
              </div>

              {/* Desktop: full holdings table */}
              <div className="surface overflow-hidden hidden md:block">
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
            </>
          )}
        </div>

        {/* Right: Holdings Map + Sector Map side-by-side (stack on narrow viewports) */}
        <div className="lg:col-span-2 lg:sticky lg:top-4 lg:self-start grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="surface p-5">
            <h3 className="section-title mb-3 text-sm">
              Holdings Map
              {activeSector !== "all" && (
                <span className="ml-2 font-normal normal-case text-muted-foreground">
                  · {activeSector}
                </span>
              )}
            </h3>
            <HoldingsTreemap
              data={treemapData}
              onClickTicker={(t) => navigate(stockPath(t))}
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
                activeName={activeSector === "all" ? null : activeSector}
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
