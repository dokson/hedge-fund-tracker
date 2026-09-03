import { useState, useMemo } from "react";
import { useParams, useNavigate, Link } from "react-router";
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
import { canonicalUrl } from "@/lib/seo";
import { usePageMeta, pageTitle } from "@/hooks/usePageMeta";
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
import { TableFrame } from "@/components/ui/TableFrame";
import { PanelTitle } from "@/components/ui/PanelTitle";
import { HoldingsTreemap } from "@/components/HoldingsTreemap";

import { ArrowLeft, Wallet, Star, X, ArrowUp, ArrowDown, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useStarred } from "@/hooks/useStarred";
import { StarButton } from "@/components/StarButton";

// ────────────────────────── Fund Grid ──────────────────────────

interface FundMeta {
  aum: number;
  holdings: number;
  latestQuarter: string | null;
}

/** Last filed quarter; a tinted pill marks a fund already current with the board. */
function LastFiling({ quarter, current }: { quarter: string | null; current: boolean }) {
  if (!quarter) return <span className="text-muted-foreground">—</span>;
  const label = quarter.replace("Q", " Q");
  if (!current) {
    return (
      <span className="text-muted-foreground" title="Latest quarter this fund has filed">
        {label}
      </span>
    );
  }
  return (
    <span
      className="chip text-positive"
      title="This fund has already filed the most recent quarter"
    >
      Filed {label}
    </span>
  );
}

/** Sort arrow for a sortable header or sort chip. */
function SortIndicator({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return null;
  const Icon = dir === "desc" ? ArrowDown : ArrowUp;
  return <Icon aria-hidden="true" className="h-3 w-3 shrink-0" />;
}

function FundLogoSquare({ fund }: { fund: HedgeFund }) {
  return (
    <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-sm border border-border bg-card">
      <FundLogo fundName={fund.fund} url={fund.url} size={24} />
    </span>
  );
}

/**
 * The fund roster as one dense board: a table from `md` up, frame rows below.
 * The same list serves every tab; `withRank` adds the AUM position.
 */
function FundList({
  list,
  metaMap,
  overallLatestQuarter,
  withRank,
  isStarred,
  onToggleStar,
}: {
  list: HedgeFund[];
  metaMap: Map<string, FundMeta>;
  overallLatestQuarter: string | null;
  withRank: boolean;
  isStarred: (fund: string) => boolean;
  onToggleStar: (fund: string) => void;
}) {
  if (list.length === 0) {
    return <EmptyState padding="sm" className="mt-4" title="No funds match your search." />;
  }
  const isCurrent = (meta: FundMeta | undefined) =>
    !!meta?.latestQuarter && meta.latestQuarter === overallLatestQuarter;

  return (
    <>
      <ol className="md:hidden mt-4 border-t border-border" aria-label="Tracked funds">
        {list.map((fund, i) => {
          const meta = metaMap.get(fund.fund);
          return (
            <li key={fund.cik} className="border-b border-border/60 py-2 flex items-start gap-3">
              <FundLogoSquare fund={fund} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  {withRank && (
                    <span className="text-xs text-muted-foreground shrink-0">{i + 1}</span>
                  )}
                  <Link to={fundPath(fund.fund)} className="fund-link truncate">
                    {fund.denomination}
                  </Link>
                </div>
                <p className="text-xs text-muted-foreground truncate">{fund.manager}</p>
                <p className="text-xs mt-1 flex flex-wrap gap-x-3">
                  <span>
                    <span className="text-muted-foreground">Holdings </span>
                    {meta ? meta.holdings : "…"}
                  </span>
                  <span>
                    <span className="text-muted-foreground">Value </span>
                    {meta ? formatValue(meta.aum) : "…"}
                  </span>
                  <span>
                    <span className="text-muted-foreground">Filed </span>
                    <LastFiling quarter={meta?.latestQuarter ?? null} current={isCurrent(meta)} />
                  </span>
                </p>
              </div>
              <StarButton
                active={isStarred(fund.fund)}
                onClick={() => onToggleStar(fund.fund)}
                size={16}
                className="h-8 w-8 m-0 shrink-0"
              />
            </li>
          );
        })}
      </ol>

      <div className="hidden md:block mt-4 frame">
        <TableFrame label="Tracked funds">
          <table className="w-full text-sm" aria-label="Tracked funds">
            <thead>
              <tr className="text-xs">
                <th scope="col" className="px-3 py-2 w-10">
                  <span className="sr-only">Starred</span>
                </th>
                {withRank && (
                  <th scope="col" className="text-right px-3 py-2 w-12">
                    #
                  </th>
                )}
                <th scope="col" className="text-left px-3 py-2">
                  Fund
                </th>
                <th scope="col" className="text-left px-3 py-2">
                  Manager
                </th>
                <th scope="col" className="text-right px-3 py-2">
                  Holdings
                </th>
                <th scope="col" className="text-right px-3 py-2">
                  Portfolio value
                </th>
                <th scope="col" className="text-right px-3 py-2">
                  Last filing
                </th>
              </tr>
            </thead>
            <tbody>
              {list.map((fund, i) => {
                const meta = metaMap.get(fund.fund);
                return (
                  <tr key={fund.cik} className="data-table-row">
                    <td className="px-3 py-1">
                      <StarButton
                        active={isStarred(fund.fund)}
                        onClick={() => onToggleStar(fund.fund)}
                        size={16}
                        className="h-8 w-8 m-0"
                      />
                    </td>
                    {withRank && (
                      <td className="px-3 py-1 text-right text-xs text-muted-foreground">
                        {i + 1}
                      </td>
                    )}
                    <td className="px-3 py-1">
                      <span className="inline-flex items-center gap-3 min-w-0 max-w-full">
                        <FundLogoSquare fund={fund} />
                        <Link to={fundPath(fund.fund)} className="fund-link truncate">
                          {fund.denomination}
                        </Link>
                      </span>
                    </td>
                    <td className="px-3 py-1 text-muted-foreground">
                      <span className="block truncate max-w-[24ch] xl:max-w-none">
                        {fund.manager}
                      </span>
                    </td>
                    <td className="px-3 py-1 text-right">{meta ? meta.holdings : "…"}</td>
                    <td className="px-3 py-1 text-right">{meta ? formatValue(meta.aum) : "…"}</td>
                    <td className="px-3 py-1 text-right">
                      <LastFiling quarter={meta?.latestQuarter ?? null} current={isCurrent(meta)} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TableFrame>
      </div>
    </>
  );
}

function FundGrid() {
  usePageMeta({
    title: pageTitle("Fund Portfolios"),
    description:
      "Every tracked hedge fund's portfolio: position count, total institutional value, quarter-over-quarter change and the manager behind it.",
    canonical: canonicalUrl(ROUTES.funds),
  });

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
            const positions = holdings.filter(
              (h) => h.cusip !== "Total" && h.delta !== "CLOSE" && parseValueString(h.value) > 0,
            );
            const total = positions.reduce((sum, h) => sum + parseValueString(h.value), 0);
            metaMap.set(fund.fund, {
              aum: total,
              holdings: positions.length,
              latestQuarter: latest,
            });
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

  const renderList = (list: HedgeFund[], withRank = false) => (
    <FundList
      list={list}
      metaMap={fundMetaMap}
      overallLatestQuarter={overallLatestQuarter ?? null}
      withRank={withRank}
      isStarred={isStarred}
      onToggleStar={toggleStar}
    />
  );

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div>
        <h1 className="page-title">
          <Wallet aria-hidden="true" className="h-5 w-5 text-muted-foreground" />
          Hedge Fund Portfolios
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          {funds.length} tracked institutional investors. A green Filed pill marks a fund already
          current with{" "}
          {overallLatestQuarter ? overallLatestQuarter.replace("Q", " Q") : "the latest quarter"}.
        </p>
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
        <div className="flex flex-wrap items-center gap-3">
          <TabsList aria-label="Sort funds">
            {starred.size > 0 && (
              <TabsTrigger value="starred" className="gap-1.5">
                <Star className="h-3.5 w-3.5" fill="currentColor" aria-hidden="true" /> Starred
                <span className="text-[11px]">({starred.size})</span>
              </TabsTrigger>
            )}
            <TabsTrigger value="updated">Last Updated</TabsTrigger>
            <TabsTrigger value="alphabetical">Alphabetical</TabsTrigger>
            <TabsTrigger value="byvalue">AUM</TabsTrigger>
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
            renderList(starredFunds)
          )}
        </TabsContent>

        {isLoading ? (
          <LoadingState message="Loading funds…" />
        ) : (
          <>
            <TabsContent value="updated">{renderList(filtered)}</TabsContent>
            <TabsContent value="alphabetical">{renderList(filtered)}</TabsContent>
            <TabsContent value="byvalue">{renderList(filtered, true)}</TabsContent>
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
 * Mobile row for a single holding. The desktop holdings table is hidden below
 * `md` and replaced by a list of these frame rows: ticker + portfolio weight
 * on the headline, company beneath, value and Δ as a two-up footer.
 */
function HoldingCard({ h, rank }: { h: QuarterlyHolding; rank: number }) {
  const isNew = h.delta === "NEW";
  const isClosed = h.delta === "CLOSE";
  const deltaParsed = isNew || isClosed ? 0 : parseFloat(h.delta) || 0;
  return (
    <li className="border-b border-border/60 py-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs text-muted-foreground shrink-0 w-[3ch] text-right">{rank}</span>
          <TickerLink ticker={h.ticker} />
        </div>
        <span className="text-sm font-medium shrink-0">{h.portfolioPct.toFixed(1)}%</span>
      </div>
      <div className="mt-1 pl-[calc(3ch+0.5rem)]">
        <CompanyLink ticker={h.ticker} company={toInitCap(h.company)} showStar />
      </div>
      <dl className="mt-1 pl-[calc(3ch+0.5rem)] flex items-start justify-between gap-3 text-sm">
        <div>
          <dt className="metric-label !text-[11px]">Value</dt>
          <dd>{h.value}</dd>
        </div>
        <div className="text-right">
          <dt className="metric-label !text-[11px]">Δ</dt>
          <dd>
            <HoldingDeltaCell
              isNew={isNew}
              isClosed={isClosed}
              deltaPct={deltaParsed}
              deltaValueRaw={h.deltaValue}
            />
          </dd>
        </div>
      </dl>
    </li>
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

  const fundLabel = fund?.denomination || formatFundName(fundName);
  usePageMeta({
    title: pageTitle(fundLabel),
    description: `${fundLabel}'s reported holdings from its latest SEC 13F filing: positions, portfolio weights and quarter-over-quarter changes.`,
    canonical: canonicalUrl(fundPath(fundName)),
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
  // Holdings map mirrors the active sector filter so it stays coherent with the
  // central list and the Sector map selection.
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

  const ariaSort = (key: SortKey) =>
    sortKey === key ? (sortDir === "desc" ? "descending" : "ascending") : "none";

  const quarterLabel = selectedQuarter ? selectedQuarter.replace("Q", " Q") : "—";

  if (quartersLoading) {
    return <LoadingState message="Loading available quarters…" />;
  }

  if (availableQuarters.length === 0) {
    return (
      <div className="space-y-6 max-w-screen-2xl">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Back to funds"
            onClick={() => navigate(ROUTES.funds)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-sm border border-border bg-card">
            <FundLogo fundName={fundName} url={fund?.url} size={28} />
          </span>
          <h1 className="page-title">
            {fund?.denomination || formatFundName(fundName)}
            <StarButton
              active={isStarred(fundName)}
              onClick={() => toggleStar(fundName)}
              size={20}
              className="h-8 w-8 m-0"
            />
          </h1>
        </div>
        <EmptyState padding="sm" title="No quarterly data available for this fund." />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Back to funds"
            onClick={() => navigate(ROUTES.funds)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-sm border border-border bg-card">
            <FundLogo fundName={fundName} url={fund?.url} size={28} />
          </span>
          <div>
            <h1 className="page-title">
              {fund?.denomination || formatFundName(fundName)}
              <StarButton
                active={isStarred(fundName)}
                onClick={() => toggleStar(fundName)}
                size={20}
                className="h-8 w-8 m-0"
              />
            </h1>
            {fund && (
              <p className="text-sm text-muted-foreground mt-0.5">Managed by {fund.manager}</p>
            )}
          </div>
        </div>
        <div className="flex gap-3 w-full sm:w-auto">
          <Select value={selectedQuarter || ""} onValueChange={setQuarter}>
            <SelectTrigger aria-label="Quarter" className="flex-1 sm:flex-none sm:w-36">
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
        <div className="min-w-0 lg:col-span-3 space-y-5">
          {/* Status cells: 2 static + 4 toggle filters, one hairline grid. */}
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-3 lg:grid-cols-6">
            <div className="bg-card p-3 flex flex-col">
              <p className="metric-label">AUM</p>
              <p className="text-lg leading-6">{formatValue(totalValue)}</p>
            </div>
            <div className="bg-card p-3 flex flex-col">
              <p className="metric-label">Positions</p>
              <p className="text-lg leading-6">
                {holdings.filter((h) => parseValueString(h.value) > 0).length}
              </p>
            </div>
            {(
              [
                { key: "new", label: "New", count: newPositions, num: "text-muted-foreground" },
                { key: "closed", label: "Closed", count: closedPositions, num: "text-closed" },
                {
                  key: "increased",
                  label: "Increased",
                  count: increasedPositions,
                  num: "text-positive",
                },
                {
                  key: "decreased",
                  label: "Decreased",
                  count: decreasedPositions,
                  num: "text-negative",
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
                  className={`p-3 flex flex-col text-left transition-colors ${active ? "bg-primary text-primary-foreground" : "bg-card hover:bg-muted"}`}
                >
                  <p
                    className={`metric-label inline-flex items-center gap-1 ${active ? "!text-primary-foreground" : ""}`}
                  >
                    <Check
                      aria-hidden="true"
                      className={`h-3.5 w-3.5 shrink-0 ${active ? "" : "opacity-0"}`}
                    />
                    {f.label}
                  </p>
                  <p className={`text-lg leading-6 ${active ? "" : f.num}`}>{f.count}</p>
                </button>
              );
            })}
          </div>

          {/* Active sector filter, mirrors the Stocks page pattern. */}
          {activeSector !== "all" && (
            <p className="status-line flex items-center gap-2 flex-wrap">
              <span className="k">Sector:</span>
              <span className="text-foreground">{activeSector}</span>
              <span aria-hidden="true">·</span>
              <span className="k">
                {activeSectorCount} holding{activeSectorCount === 1 ? "" : "s"}
              </span>
              <button
                type="button"
                onClick={() => setSectorFilter("all")}
                aria-label="Clear sector filter"
                className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <X className="h-3 w-3" aria-hidden="true" /> Clear
              </button>
            </p>
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
              {/* Mobile: sort controls + frame rows */}
              <div className="md:hidden space-y-3">
                <div className="flex items-center gap-2 overflow-x-auto">
                  <span className="control-label shrink-0">Sort</span>
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
                        type="button"
                        onClick={() => toggleSort(key)}
                        aria-pressed={active}
                        className={`inline-flex items-center gap-1 h-9 px-3 rounded-md border text-xs transition-colors shrink-0 ${
                          active
                            ? "bg-primary text-primary-foreground border-primary"
                            : "border-border bg-card text-muted-foreground"
                        }`}
                      >
                        {label}
                        <SortIndicator active={active} dir={sortDir} />
                      </button>
                    );
                  })}
                </div>
                <ol className="border-t border-border" aria-label="Holdings">
                  {(showAll ? sorted : sorted.slice(0, TOP_N)).map((h, i) => (
                    <HoldingCard key={`${h.cusip}-${h.ticker}-${h.delta}`} h={h} rank={i + 1} />
                  ))}
                </ol>
                {!showAll && sorted.length > TOP_N && (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="w-full"
                    onClick={() => setShowAll(true)}
                  >
                    Show all {sorted.length} positions
                  </Button>
                )}
              </div>

              {/* Desktop: full holdings table */}
              <div className="frame hidden md:block">
                <TableFrame label={`Holdings for ${quarterLabel}`}>
                  <table className="w-full text-sm" aria-label={`Holdings for ${quarterLabel}`}>
                    <thead>
                      <tr className="text-xs">
                        <th scope="col" className="text-left px-3 py-2">
                          #
                        </th>
                        <th scope="col" className="text-left px-3 py-2">
                          Ticker
                        </th>
                        <th scope="col" className="text-left px-3 py-2">
                          Company
                        </th>
                        <th scope="col" className="text-right px-3 py-2">
                          Value
                        </th>
                        <th
                          scope="col"
                          aria-sort={ariaSort("delta")}
                          className="text-right px-3 py-2"
                        >
                          <button
                            type="button"
                            onClick={() => toggleSort("delta")}
                            className="inline-flex min-w-6 items-center justify-end gap-1 h-7 hover:text-foreground"
                          >
                            Δ
                            <SortIndicator active={sortKey === "delta"} dir={sortDir} />
                          </button>
                        </th>
                        <th
                          scope="col"
                          aria-sort={ariaSort("portfolioPct")}
                          className="text-right px-3 py-2"
                        >
                          <button
                            type="button"
                            onClick={() => toggleSort("portfolioPct")}
                            className="inline-flex min-w-6 items-center justify-end gap-1 h-7 hover:text-foreground"
                          >
                            Port %
                            <SortIndicator active={sortKey === "portfolioPct"} dir={sortDir} />
                          </button>
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
                            <td className="p-3 text-muted-foreground text-xs">{i + 1}</td>
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
                            <Button variant="secondary" size="sm" onClick={() => setShowAll(true)}>
                              Showing top {TOP_N} of {sorted.length}. Show all
                            </Button>
                          </td>
                        </tr>
                      </tfoot>
                    )}
                  </table>
                </TableFrame>
              </div>
            </>
          )}
        </div>

        {/* Right: Holdings map + Sector map side-by-side (stack on narrow viewports) */}
        <div className="min-w-0 lg:col-span-2 lg:sticky lg:top-4 lg:self-start grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="frame flex h-full flex-col overflow-hidden">
            <div className="frame-title frame-title--spaced">
              <PanelTitle>
                Holdings map
                {activeSector !== "all" && (
                  <span className="font-normal text-muted-foreground"> · {activeSector}</span>
                )}
              </PanelTitle>
            </div>
            <div className="flex-1 min-h-0 p-3 pt-0">
              <HoldingsTreemap
                data={treemapData}
                onClickTicker={(t) => navigate(stockPath(t))}
                displayMode="pct"
              />
            </div>
          </div>
          {sectorTreemapData.length > 0 && (
            <div className="frame flex h-full flex-col overflow-hidden">
              <div className="frame-title frame-title--spaced">
                <PanelTitle>Sector map</PanelTitle>
              </div>
              <div className="flex-1 min-h-0 p-3 pt-0">
                <HoldingsTreemap
                  data={sectorTreemapData}
                  onClickTicker={(sector) =>
                    setSectorFilter((cur) => (cur === sector ? "all" : sector))
                  }
                  displayMode="pct"
                  activeName={activeSector === "all" ? null : activeSector}
                />
              </div>
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
