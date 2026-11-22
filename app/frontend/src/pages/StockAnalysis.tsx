import { useMemo, useState } from "react";
import { useParams } from "react-router";
import { StarButton } from "@/components/StarButton";
import { useStarred } from "@/hooks/useStarred";
import { skipToken, useQuery } from "@tanstack/react-query";
import {
  runStockAnalysis,
  formatValue,
  formatPct,
  getStocks,
  type FundTickerHolding,
} from "@/lib/dataService";
import type { SmartScoreView } from "@/lib/smartScore";
import { SmartScorePill } from "@/components/SmartScorePill";
import { SmartScorePanel } from "@/components/SmartScorePanel";
import { stocksByIndustry, aiDiligenceFor, stockPath, ROUTES } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";
import { usePageMeta, pageTitle } from "@/hooks/usePageMeta";
import { getSectorStyle, sectorPillStyle, SECTOR_PILL } from "@/lib/sectorStyle";
import { isQuarter, type Quarter } from "@/lib/quarters";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { useQuarterAnalysis } from "@/hooks/useQuarterAnalysis";
import { FundCell } from "@/components/EntityLinks";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { HolderMoves } from "@/components/QuarterMoves";
import { HOLDER_MOVE_PICK, type MoveFilter } from "@/lib/moves";
import { RecentStockFilings } from "@/components/RecentStockFilings";
import { Stat, StatGrid } from "@/components/ui/Stat";
import { useAnnualReturns } from "@/hooks/useFundRanking";
import { pctFrac } from "@/lib/performanceFormat";
import { Button } from "@/components/ui/button";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { ResponsiveTable } from "@/components/ui/ResponsiveTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { LogoPlate } from "@/components/LogoPlate";
import { toneClass } from "@/lib/tone";
import { ChangeChip } from "@/components/ui/ChangeChip";
import { ArrowDown, ArrowLeft, Brain } from "lucide-react";
import { Breadcrumb } from "@/components/ui/Breadcrumb";
import { PageEnd } from "@/components/PageEnd";
import { useBack } from "@/hooks/useBack";
import { ColumnHeader } from "@/components/ui/ColumnHeader";
import { QueryState } from "@/components/ui/QueryState";
import { useSortState } from "@/hooks/useSortState";
import { announce } from "@/lib/announce";
import { CardSortBar } from "@/components/ui/CardSortBar";
import { useResearchState } from "@/hooks/useResearchState";
import { CompanyLogo } from "@/components/CompanyLogo";
import { StockPriceChart } from "@/components/StockPriceChart";
import { IS_GH_PAGES_MODE } from "@/lib/config";
import { useNavigate } from "react-router";
import { AnalysisProgress } from "@/components/ui/AnalysisProgress";
import { MetaLine, MetaSep } from "@/components/ui/TextLink";

type SortKey = "shares" | "value" | "deltaValue" | "portfolioPct" | "annualReturn";
type HoldingFilter = "all" | MoveFilter;

const HOLDING_FILTER_OPTIONS: readonly { value: HoldingFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "new", label: "New" },
  { value: "increased", label: "Added" },
  { value: "decreased", label: "Trimmed" },
  { value: "closed", label: "Sold out" },
];

/** Defer only sections outside the initial viewport. */
function deferBelowViewport(element: HTMLElement | null) {
  if (element && element.getBoundingClientRect().top >= window.innerHeight) {
    element.classList.add("defer-render");
  }
}

function signed(n: number, digits = 0) {
  return `${n > 0 ? "+" : ""}${n.toFixed(digits)}`;
}

/** A fund's return per year from the ranking, toned; a dash when it has none. */
function PerYear({ value }: { value: number | null | undefined }) {
  return value == null ? (
    <span className="text-muted-foreground">—</span>
  ) : (
    <span className={toneClass(value)}>{pctFrac(value)}</span>
  );
}

/** Mobile row for one holder: the six-column table does not fit a phone. */
function StockHolderCard({
  h,
  rank,
  perYear,
}: {
  h: FundTickerHolding;
  rank: number;
  perYear: number | null | undefined;
}) {
  const deltaNum =
    h.delta === "NEW" ? Infinity : h.delta === "CLOSE" ? -100 : parseFloat(h.delta) || 0;
  return (
    <li className="border-b border-border py-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-mono text-xs text-muted-foreground shrink-0">#{rank}</span>
          <FundCell fundName={h.fund} />
        </div>
        <span className="font-mono text-sm shrink-0">{h.portfolioPct.toFixed(2)}%</span>
      </div>
      <div className="status-line mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
        <span>
          <span className="k">Value:</span> {formatValue(h.value)}
        </span>
        <MetaSep />
        <span>
          <span className="k">Share Δ %:</span>{" "}
          {h.isNew ? (
            <ChangeChip change="NEW" />
          ) : h.isClosed ? (
            <ChangeChip change="CLOSE" />
          ) : deltaNum === 0 ? (
            <ChangeChip change="NO CHANGE" />
          ) : (
            <span className={toneClass(deltaNum)}>{h.delta}</span>
          )}
        </span>
        <MetaSep />
        <span>
          <span className="k">Position Δ $:</span>{" "}
          <span className={toneClass(h.deltaValue)}>{formatValue(h.deltaValue)}</span>
        </span>
        <MetaSep />
        <span>
          <span className="k">Fund %/yr:</span> <PerYear value={perYear} />
        </span>
      </div>
    </li>
  );
}

export default function StockAnalysis() {
  const { ticker = "NVDA" } = useParams();
  const navigate = useNavigate();
  const goBack = useBack(ROUTES.stocks);
  const { isStarred, toggle: toggleStar } = useStarred("stock");
  const { quarters, latestQuarter } = useAvailableQuarters();
  const [selectedQuarter, setSelectedQuarter] = useResearchState<Quarter | undefined>(
    "quarter",
    undefined,
  );
  const quarter = selectedQuarter ?? latestQuarter;
  const [progress, setProgress] = useState({ msg: "", pct: 0 });

  const {
    data: holdings = [],
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["stockAnalysis", ticker, quarter],
    queryFn: quarter
      ? () => runStockAnalysis(ticker, quarter, (msg, pct) => setProgress({ msg, pct }))
      : skipToken,
    staleTime: 10 * 60 * 1000,
  });

  // Sector + industry come from stocks.csv (joined with sector_hierarchy inside
  // getStocks). Same in-memory cache as the rest of the app — no extra fetch.
  const { data: stocks = [] } = useQuery({ queryKey: ["stocks"], queryFn: getStocks });
  // Score uses the shared quarter-analysis universe. The latest stock-holder
  // view independently overlays saved non-quarterly disclosures.
  const {
    data: quarterRows = [],
    isError: scoreError,
    isLoading: scoreLoading,
    error: scoreErrorDetail,
  } = useQuarterAnalysis(quarter);
  const scoreRow = quarterRows.find((r) => r.ticker === ticker);
  const smartScore: SmartScoreView | undefined =
    scoreRow?.smartScore !== undefined
      ? {
          smartScore: scoreRow.smartScore,
          breadth: scoreRow.scoreBreadth ?? null,
          momentum: scoreRow.scoreMomentum ?? null,
          conviction: scoreRow.scoreConviction ?? null,
        }
      : undefined;
  const meta = stocks.find((s) => s.ticker === ticker);
  const sector = meta?.sector;
  const industry = meta?.industry;
  const sectorStyle = getSectorStyle(sector);
  const SectorIcon = sectorStyle.icon;

  const company = holdings[0]?.company || meta?.company || ticker;

  usePageMeta({
    title: pageTitle(company === ticker ? ticker : `${ticker} · ${company}`),
    description: `Which hedge funds hold ${company} (${ticker}), how much, and how those positions moved quarter over quarter, from SEC 13F filings.`,
    canonical: canonicalUrl(stockPath(ticker)),
  });

  // One pass over holdings for every KPI the page shows.
  const kpi = useMemo(() => {
    let totalValue = 0;
    let totalDeltaValue = 0;
    let ptfSum = 0;
    let maxPtfPct = 0;
    let buyerCount = 0;
    let sellerCount = 0;
    let holderCount = 0;
    let newHolderCount = 0;
    let closeCount = 0;
    for (const h of holdings) {
      totalValue += h.value;
      totalDeltaValue += h.deltaValue;
      ptfSum += h.portfolioPct;
      if (h.portfolioPct > maxPtfPct) maxPtfPct = h.portfolioPct;
      if (h.isBuyer) buyerCount++;
      if (h.isSeller) sellerCount++;
      if (h.isHolder) holderCount++;
      if (h.isNew) newHolderCount++;
      if (h.isClosed) closeCount++;
    }
    const previousTotal = totalValue - totalDeltaValue;
    const deltaPct =
      holderCount === newHolderCount && closeCount === 0
        ? Infinity
        : previousTotal !== 0
          ? (totalDeltaValue / previousTotal) * 100
          : 0;
    return {
      totalValue,
      totalDeltaValue,
      deltaPct,
      avgPtfPct: holdings.length > 0 ? ptfSum / holdings.length : 0,
      maxPtfPct,
      buyerCount,
      sellerCount,
      holderCount,
      newHolderCount,
      closeCount,
      netBuyers: buyerCount - sellerCount,
    };
  }, [holdings]);

  const annualReturns = useAnnualReturns();

  const { sortKey, sortDir, toggleSort } = useSortState<SortKey>("portfolioPct", "desc", "holders");
  const [holdingFilter, setHoldingFilter] = useResearchState<HoldingFilter>(
    "holders:filter",
    "all",
  );

  const sortedHoldings = (() => {
    const list =
      holdingFilter === "all" ? [...holdings] : holdings.filter(HOLDER_MOVE_PICK[holdingFilter]);
    // A fund without a return per year sorts last in either direction.
    const valueOf = (h: FundTickerHolding) =>
      sortKey === "annualReturn" ? (annualReturns.get(h.fund) ?? null) : h[sortKey];
    list.sort((a, b) => {
      const va = valueOf(a);
      const vb = valueOf(b);
      if (va === null) return vb === null ? 0 : 1;
      if (vb === null) return -1;
      return sortDir === "desc" ? vb - va : va - vb;
    });
    return list;
  })();
  // A filter change says how many funds it left, through the app's one status region.
  const applyFilter = (next: HoldingFilter) => {
    setHoldingFilter(next);
    const shown = next === "all" ? holdings.length : holdings.filter(HOLDER_MOVE_PICK[next]).length;
    announce(`Showing ${shown} of ${holdings.length} funds`);
  };
  const toggleMoves = (key: MoveFilter) => applyFilter(holdingFilter === key ? "all" : key);

  const holdersTitle = `Holders by Shares (${holdings.length} funds)`;
  const scorePanel = (
    // Quarter-analysis score and the stock's independently merged holder view need not
    // have the same disclosure coverage.
    <QueryState
      isError={scoreError}
      error={scoreErrorDetail}
      title="Could not load the smart score"
    >
      <div id="smart-score" className="scroll-mt-20">
        <SmartScorePanel score={smartScore} quarterLabel={quarter} loading={scoreLoading} />
      </div>
    </QueryState>
  );

  return (
    <div className="space-y-3 max-w-screen-2xl">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            aria-label="Back"
            onClick={goBack}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <Breadcrumb trail={[{ label: "Stocks", to: ROUTES.stocks }]} current={ticker} />
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() =>
            document.getElementById("holders-heading")?.scrollIntoView({ block: "start" })
          }
        >
          <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
          Holders
        </Button>
      </div>
      <PageHeader
        title={ticker}
        description={company === ticker ? undefined : company}
        leading={
          <LogoPlate size="lg">
            <CompanyLogo ticker={ticker} size={40} eager />
          </LogoPlate>
        }
        actions={
          <>
            {smartScore && (
              <SmartScorePill
                score={smartScore.smartScore}
                ticker={ticker}
                quarterLabel={quarter}
                inPage
              />
            )}
            <StarButton
              active={isStarred(ticker)}
              subject={ticker}
              onClick={() => toggleStar(ticker)}
              size={24}
            />
          </>
        }
      >
        {(sector || industry) && (
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
            {sector && (
              <span
                className={SECTOR_PILL}
                style={sectorPillStyle(sectorStyle)}
                title={`Yahoo Finance sector: ${sector}`}
              >
                <SectorIcon className="h-3 w-3" aria-hidden="true" />
                {sector}
              </span>
            )}
            {industry && (
              <button
                type="button"
                onClick={() => navigate(stocksByIndustry(industry))}
                className="inline-flex min-h-6 items-center text-xs font-medium text-muted-foreground transition-colors duration-[120ms] hover:text-foreground hover:underline"
                title={`Browse all ${industry} stocks`}
              >
                {industry}
              </button>
            )}
          </div>
        )}
      </PageHeader>
      <div className="flex flex-wrap justify-end gap-3">
        <div className="flex gap-3 w-full sm:w-auto">
          <Select
            value={quarter ?? ""}
            onValueChange={(v) => {
              if (isQuarter(v)) setSelectedQuarter(v);
            }}
          >
            <SelectTrigger className="flex-1 sm:flex-none sm:w-36 bg-card" aria-label="Quarter">
              {/* The label itself, not Radix's match: before the quarter list loads there is no
                  item to match and the trigger would read blank. */}
              <SelectValue placeholder="Quarter">{quarter?.replace("Q", " Q")}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {quarters.toReversed().map((q) => (
                <SelectItem key={q} value={q}>
                  {q.replace("Q", " Q")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {/* The static build has no AI backend: a button to a disabled page would mislead. */}
          {!IS_GH_PAGES_MODE && (
            <Button
              variant="outline"
              className="h-9 flex-1 sm:flex-none whitespace-nowrap text-magenta"
              onClick={() => navigate(aiDiligenceFor(ticker))}
            >
              <Brain className="h-4 w-4" aria-hidden="true" /> AI Due Diligence
            </Button>
          )}
        </div>
      </div>

      {/* With no holders to show, the score still explains itself above the message. */}
      {(isError || isLoading || holdings.length === 0) && scorePanel}
      {isError ? (
        <QueryState isError error={error} title="Could not load this stock's holders" />
      ) : isLoading ? (
        <div className="surface p-8">
          <AnalysisProgress msg={progress.msg} pct={progress.pct} />
        </div>
      ) : holdings.length === 0 ? (
        <div className="surface p-8 text-center text-muted-foreground">
          No fund holds {ticker} in {quarter?.replace("Q", " Q") ?? "this quarter"}. Try a different
          quarter.
        </div>
      ) : (
        <>
          <MetaLine className="block">
            Position changes in {quarter?.replace("Q", " Q")}, reconstructed between disclosures at
            reporting prices, not returns or executed trades.
            {quarter === latestQuarter && " Includes saved 13D/G and Form 4 updates."}
          </MetaLine>
          <StatGrid className="grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
            <Stat
              label="Holders"
              value={kpi.holderCount}
              hint={`${kpi.newHolderCount} new, ${kpi.closeCount} sold out`}
            />
            <Stat label="Total held" value={formatValue(kpi.totalValue)} />
            <Stat
              label="Position change"
              info="Share changes valued at reporting prices. The percentage divides that change by the implied prior position value; it is not aggregate share growth or a return."
              value={formatValue(kpi.totalDeltaValue)}
              valueClassName={toneClass(kpi.totalDeltaValue)}
              hint={formatPct(kpi.deltaPct, true)}
            />
            <Stat
              label="Net buyers"
              info="Funds that opened or increased the position minus funds that reduced or closed it."
              value={signed(kpi.netBuyers)}
              valueClassName={toneClass(kpi.netBuyers)}
              hint={`${kpi.buyerCount} increased, ${kpi.sellerCount} reduced`}
            />
            <Stat
              label="Avg weight"
              value={`${kpi.avgPtfPct.toFixed(2)}%`}
              hint={`max ${kpi.maxPtfPct.toFixed(1)}%`}
            />
            <Stat
              label="Smart Score"
              value={
                smartScore ? (
                  <a
                    href="#smart-score"
                    // The name keeps the visible figure (SC 2.5.3) and says where it leads.
                    aria-label={`Smart Score ${smartScore.smartScore.toFixed(1)} out of 10, see the breakdown`}
                    className="underline underline-offset-2"
                  >
                    {smartScore.smartScore.toFixed(1)}
                  </a>
                ) : (
                  "—"
                )
              }
              hint="out of 10, see below"
            />
          </StatGrid>

          <RecentStockFilings ticker={ticker} />
          <HolderMoves
            holdings={holdings}
            annualReturns={annualReturns}
            quarterLabel={quarter?.replace("Q", " Q") ?? ""}
            active={holdingFilter}
            onToggle={toggleMoves}
          />

          {scorePanel}

          {/* The static build has no backend: no chart, and no apology card either. */}
          {!IS_GH_PAGES_MODE && <StockPriceChart ticker={ticker} />}

          <section
            aria-labelledby="holders-heading"
            // The header and toolbar precede different card and table row heights.
            ref={deferBelowViewport}
            className="space-y-3 [--defer-h:var(--defer-mobile)] md:[--defer-h:var(--defer-desktop)]"
            style={
              {
                "--defer-mobile": `${sortedHoldings.length * 90 + 180}px`,
                "--defer-desktop": `${sortedHoldings.length * 57 + 120}px`,
              } as React.CSSProperties
            }
          >
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <h2 id="holders-heading" className="section-title">
                  {holdersTitle}
                </h2>
                {holdingFilter !== "all" && (
                  <MetaLine className="block">
                    Showing {sortedHoldings.length} of {holdings.length} funds
                  </MetaLine>
                )}
              </div>
              <SegmentedControl
                size="sm"
                aria-label="Filter holders"
                value={holdingFilter}
                onValueChange={applyFilter}
                options={HOLDING_FILTER_OPTIONS}
                // Five segments overflow a phone's width: they wrap to two rows there.
                className="max-md:h-auto max-md:flex-wrap max-md:overflow-visible max-md:[&>button]:min-h-6"
              />
            </div>

            <ResponsiveTable
              label={holdersTitle}
              tableClassName="surface"
              cards={
                <div className="space-y-3">
                  <CardSortBar
                    options={[
                      { key: "portfolioPct", label: "Ptf %" },
                      { key: "value", label: "Value" },
                      { key: "deltaValue", label: "Position Δ $" },
                      { key: "annualReturn", label: "Fund %/yr" },
                    ]}
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onToggle={toggleSort}
                  />
                  <ul className="border-t border-border">
                    {sortedHoldings.map((h, i) => (
                      <StockHolderCard
                        key={`${h.fund}-${h.delta}-${h.value}`}
                        h={h}
                        rank={i + 1}
                        perYear={annualReturns.get(h.fund)}
                      />
                    ))}
                  </ul>
                </div>
              }
              table={
                <table className="w-full text-sm" aria-label={holdersTitle}>
                  <thead>
                    <tr>
                      <th scope="col" className="text-right p-3 w-12">
                        #
                      </th>
                      <th scope="col" className="text-left p-3">
                        Fund
                      </th>
                      {(
                        [
                          ["portfolioPct", "Ptf %"],
                          ["value", "Value"],
                        ] as const
                      ).map(([key, label]) => (
                        <ColumnHeader
                          key={key}
                          label={label}
                          align="right"
                          sort={{
                            active: sortKey === key,
                            direction: sortDir,
                            onToggle: () => toggleSort(key),
                          }}
                        />
                      ))}
                      <th scope="col" className="text-right p-3">
                        Share Δ %
                      </th>
                      <ColumnHeader
                        label="Position Δ $"
                        align="right"
                        sort={{
                          active: sortKey === "deltaValue",
                          direction: sortDir,
                          onToggle: () => toggleSort("deltaValue"),
                        }}
                      />
                      <ColumnHeader
                        label="Fund %/yr"
                        align="right"
                        sort={{
                          active: sortKey === "annualReturn",
                          direction: sortDir,
                          onToggle: () => toggleSort("annualReturn"),
                        }}
                      />
                    </tr>
                  </thead>
                  <tbody>
                    {sortedHoldings.map((h, i) => {
                      const deltaNum =
                        h.delta === "NEW"
                          ? Infinity
                          : h.delta === "CLOSE"
                            ? -100
                            : parseFloat(h.delta) || 0;
                      return (
                        <tr key={`${h.fund}-${h.delta}-${h.value}`} className="data-table-row">
                          <td className="p-3 text-right text-muted-foreground font-mono text-xs">
                            {i + 1}
                          </td>
                          <td className="p-3">
                            <FundCell fundName={h.fund} />
                          </td>
                          <td className="p-3 text-right font-mono">{h.portfolioPct.toFixed(2)}%</td>
                          <td className="p-3 text-right font-mono">{formatValue(h.value)}</td>
                          <td className="p-3 text-right font-mono">
                            {h.isNew ? (
                              <ChangeChip change="NEW" />
                            ) : h.isClosed ? (
                              <ChangeChip change="CLOSE" />
                            ) : deltaNum === 0 ? (
                              <ChangeChip change="NO CHANGE" />
                            ) : (
                              <span className={toneClass(deltaNum)}>{h.delta}</span>
                            )}
                          </td>
                          <td className={`p-3 text-right font-mono ${toneClass(h.deltaValue)}`}>
                            {formatValue(h.deltaValue)}
                          </td>
                          <td className="p-3 text-right font-mono">
                            <PerYear value={annualReturns.get(h.fund)} />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              }
            />
          </section>
        </>
      )}
      <PageEnd
        links={[
          ...(industry ? [{ label: `More in ${industry}`, to: stocksByIndustry(industry) }] : []),
          { label: "All stocks", to: ROUTES.stocks },
          { label: "Fund ranking", to: ROUTES.fundRanking },
        ]}
      />
    </div>
  );
}
