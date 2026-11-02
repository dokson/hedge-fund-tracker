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
import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from "recharts";
import { MeasuredChart } from "@/components/MeasuredChart";
import { Button } from "@/components/ui/button";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { TableFrame } from "@/components/ui/TableFrame";
import { ArrowDown, ArrowLeft, Brain } from "lucide-react";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { Breadcrumb } from "@/components/ui/Breadcrumb";
import { PageEnd } from "@/components/PageEnd";
import { useBack } from "@/hooks/useBack";
import { SortArrow } from "@/components/ui/SortArrow";
import { QueryState } from "@/components/ui/QueryState";
import { useSortState } from "@/hooks/useSortState";
import { useResearchState } from "@/hooks/useResearchState";
import { CompanyLogo } from "@/components/CompanyLogo";
import { StockPriceChart } from "@/components/StockPriceChart";
import { IS_GH_PAGES_MODE } from "@/lib/config";
import { useNavigate } from "react-router";
import { AnalysisProgress } from "@/components/ui/AnalysisProgress";

type SortKey = "shares" | "value" | "deltaValue" | "portfolioPct";
type HoldingFilter = "all" | "buyers" | "sellers" | "new" | "closed";

const HOLDING_FILTER_OPTIONS: readonly { value: HoldingFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "buyers", label: "Buyers" },
  { value: "new", label: "New" },
  { value: "sellers", label: "Sellers" },
  { value: "closed", label: "Sold out" },
];

const TOOLTIP_STYLE = {
  background: "hsl(var(--popover))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "var(--radius)",
  boxShadow: "0 2px 8px rgba(0,0,0,.35)",
  fontSize: 12,
  color: "hsl(var(--foreground))",
  padding: "6px 10px",
  lineHeight: 1.6,
} as const;

function signed(n: number, digits = 0) {
  return `${n > 0 ? "+" : ""}${n.toFixed(digits)}`;
}

function deltaClass(n: number) {
  return n > 0 ? "delta-positive" : n < 0 ? "delta-negative" : "";
}

/** Dot legend under a chart, so the colours are named, not only seen. */
function ChartLegend({ items }: { items: readonly { swatch: string; label: string }[] }) {
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {items.map((it) => (
        <li key={it.label} className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
            style={{ background: it.swatch }}
          />
          {it.label}
        </li>
      ))}
    </ul>
  );
}

/** Mobile row for one holder: the six-column table does not fit a phone. */
function StockHolderCard({ h, rank }: { h: FundTickerHolding; rank: number }) {
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
        <span aria-hidden="true">·</span>
        <span>
          <span className="k">Share Δ %:</span>{" "}
          {h.isNew ? (
            <span className="badge-new">NEW</span>
          ) : h.isClosed ? (
            <span className="badge-closed">CLOSE</span>
          ) : deltaNum === 0 ? (
            <span className="badge-nochange">NO CHANGE</span>
          ) : (
            <span className={deltaNum > 0 ? "delta-positive" : "delta-negative"}>{h.delta}</span>
          )}
        </span>
        <span aria-hidden="true">·</span>
        <span>
          <span className="k">Position Δ $:</span>{" "}
          <span className={deltaClass(h.deltaValue)}>{formatValue(h.deltaValue)}</span>
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

  const company = holdings[0]?.company || ticker;

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
    let totalValueBought = 0;
    let totalValueSold = 0;
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
      if (h.deltaValue > 0) totalValueBought += h.deltaValue;
      else totalValueSold -= h.deltaValue;
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
      bsRatio: sellerCount > 0 ? buyerCount / sellerCount : Infinity,
      totalValueBought,
      totalValueSold,
    };
  }, [holdings]);

  const sentimentData = [
    {
      label: "Buyers",
      buyers: kpi.buyerCount - kpi.newHolderCount,
      new: kpi.newHolderCount,
      sellers: 0,
      closed: 0,
    },
    {
      label: "Sellers",
      buyers: 0,
      new: 0,
      sellers: kpi.sellerCount - kpi.closeCount,
      closed: kpi.closeCount,
    },
  ];

  const valueFlowData = [
    { label: "Added", value: kpi.totalValueBought, fill: "hsl(var(--positive))" },
    { label: "Reduced", value: kpi.totalValueSold, fill: "hsl(var(--negative))" },
  ];

  const { sortKey, sortDir, toggleSort, ariaSort } = useSortState<SortKey>(
    "portfolioPct",
    "desc",
    "holders",
  );
  const [holdingFilter, setHoldingFilter] = useResearchState<HoldingFilter>(
    "holders:filter",
    "all",
  );

  const sortedHoldings = (() => {
    let list = [...holdings];
    switch (holdingFilter) {
      case "buyers":
        list = list.filter((h) => h.isBuyer);
        break;
      case "sellers":
        list = list.filter((h) => h.isSeller);
        break;
      case "new":
        list = list.filter((h) => h.isNew);
        break;
      case "closed":
        list = list.filter((h) => h.isClosed);
        break;
    }
    list.sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      return sortDir === "desc" ? vb - va : va - vb;
    });
    return list;
  })();

  const holdersTitle = `Holders by Shares (${holdings.length} funds)`;
  const sortableTh = (keyName: SortKey, label: string) => (
    <th scope="col" aria-sort={ariaSort(keyName)} className="text-right p-0">
      <button
        type="button"
        onClick={() => toggleSort(keyName)}
        className="w-full p-3 text-right whitespace-nowrap hover:text-foreground hover:bg-muted"
      >
        {label}
        <SortArrow active={sortKey === keyName} direction={sortDir} />
      </button>
    </th>
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid min-w-0 w-full grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3 sm:w-auto sm:flex-1">
          <div className="border border-border bg-card p-1.5">
            <CompanyLogo ticker={ticker} size={44} />
          </div>
          <div className="min-w-0 space-y-1">
            <h1 className="page-title flex-wrap gap-x-2 gap-y-0">
              {ticker}
              <span className="text-sm font-normal leading-5 text-muted-foreground sm:text-base">
                {company}
              </span>
            </h1>
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
          </div>
          <StarButton active={isStarred(ticker)} onClick={() => toggleStar(ticker)} size={24} />
        </div>
        <div className="flex gap-3 w-full sm:w-auto">
          <Select
            value={quarter ?? ""}
            onValueChange={(v) => {
              if (isQuarter(v)) setSelectedQuarter(v);
            }}
          >
            <SelectTrigger
              className="flex-1 sm:flex-none sm:w-36 bg-card border-border"
              aria-label="Quarter"
            >
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
          <Button
            variant="outline"
            className="h-9 flex-1 sm:flex-none whitespace-nowrap text-magenta"
            onClick={() => navigate(aiDiligenceFor(ticker))}
          >
            <Brain className="h-4 w-4" aria-hidden="true" /> AI Due Diligence
          </Button>
        </div>
      </div>

      {/* Quarter-analysis score and the stock's independently merged holder
          view need not have the same disclosure coverage. */}
      <QueryState
        isError={scoreError}
        error={scoreErrorDetail}
        title="Could not load the smart score"
      >
        <SmartScorePanel score={smartScore} quarterLabel={quarter} loading={scoreLoading} />
      </QueryState>

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
          <section aria-labelledby="flow-heading" className="space-y-3">
            <div>
              <h2 id="flow-heading" className="section-title">
                Institutional position changes, {quarter?.replace("Q", " Q")}
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Reconstructed between disclosures at reporting prices — not returns or executed
                trades.
                {quarter === latestQuarter && " Includes saved 13D/G and Form 4 updates."}
              </p>
            </div>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 border-y border-border py-4 sm:grid-cols-[auto_auto_1fr] sm:gap-x-10">
              <div>
                <dt className="metric-label flex h-5 items-center">Total held</dt>
                <dd className="mt-1 text-2xl font-semibold tabular-nums">
                  {formatValue(kpi.totalValue)}
                </dd>
              </div>
              <div>
                <dt className="metric-label flex h-5 items-center gap-1">
                  Position change
                  <InfoTooltip text="Share changes valued at reporting prices. The percentage divides that change by the implied prior position value; it is not aggregate share growth or a return." />
                </dt>
                <dd className="mt-1 flex items-baseline gap-2 tabular-nums">
                  <span className={`text-2xl font-semibold ${deltaClass(kpi.totalDeltaValue)}`}>
                    {formatValue(kpi.totalDeltaValue)}
                  </span>
                  <span className={`text-sm ${deltaClass(kpi.deltaPct)}`}>
                    {formatPct(kpi.deltaPct, true)}
                  </span>
                </dd>
              </div>
              <div className="col-span-2 sm:col-span-1">
                <dt className="metric-label flex h-5 items-center gap-1">
                  Net buyers
                  <InfoTooltip text="Funds that opened or increased the position minus funds that reduced or closed it." />
                </dt>
                <dd className="mt-1 flex flex-wrap items-baseline gap-x-2 tabular-nums">
                  <span className={`text-2xl font-semibold ${deltaClass(kpi.netBuyers)}`}>
                    {signed(kpi.netBuyers)}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {kpi.buyerCount} increased · {kpi.sellerCount} reduced
                  </span>
                </dd>
              </div>
            </dl>
            <dl className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted-foreground">
              {[
                ["Holders", kpi.holderCount],
                ["New", kpi.newHolderCount],
                ["Sold out", kpi.closeCount],
                ["Buy/sell ratio", isFinite(kpi.bsRatio) ? `${kpi.bsRatio.toFixed(1)}×` : "∞"],
                ["Avg weight", `${kpi.avgPtfPct.toFixed(2)}%`],
                ["Max weight", `${kpi.maxPtfPct.toFixed(1)}%`],
              ].map(([label, value]) => (
                <div key={label} className="flex items-baseline gap-1.5">
                  <dt>{label}</dt>
                  <dd className="font-medium tabular-nums text-foreground">{value}</dd>
                </div>
              ))}
            </dl>
          </section>

          {/* The static build has no backend: no chart, and no apology card either. */}
          {!IS_GH_PAGES_MODE && <StockPriceChart ticker={ticker} />}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <section className="frame" aria-labelledby="sentiment-heading">
              <h2 id="sentiment-heading" className="frame-title">
                Funds increasing vs reducing
              </h2>
              <div className="p-3">
                <div className="h-[80px]">
                  <MeasuredChart>
                    {({ width, height }) => (
                      <BarChart
                        width={width}
                        height={height}
                        data={sentimentData}
                        layout="vertical"
                      >
                        <XAxis type="number" hide />
                        <YAxis
                          type="category"
                          dataKey="label"
                          width={60}
                          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          cursor={{ fill: "hsl(var(--muted))" }}
                          content={({ active, payload }) => {
                            if (!active || !payload?.length) return null;
                            const row = payload[0]?.payload;
                            const isBuyers = row.label === "Buyers";
                            return (
                              <div style={TOOLTIP_STYLE}>
                                <div>
                                  <span style={{ fontWeight: 700 }}>
                                    {isBuyers ? "Increase" : "Decrease"}
                                  </span>{" "}
                                  : {isBuyers ? row.buyers : row.sellers}
                                </div>
                                <div>
                                  <span style={{ fontWeight: 700 }}>
                                    {isBuyers ? "New" : "Close"}
                                  </span>{" "}
                                  : {isBuyers ? row.new : row.closed}
                                </div>
                              </div>
                            );
                          }}
                        />
                        <Bar
                          dataKey="buyers"
                          name="Buyers"
                          stackId="a"
                          barSize={24}
                          fill="hsl(var(--positive))"
                          radius={0}
                        />
                        <Bar
                          dataKey="new"
                          name="New"
                          stackId="a"
                          fill="hsl(var(--positive) / 0.55)"
                          radius={0}
                        />
                        <Bar
                          dataKey="sellers"
                          name="Sellers"
                          stackId="a"
                          fill="hsl(var(--negative))"
                          radius={0}
                        />
                        <Bar
                          dataKey="closed"
                          name="Closed"
                          stackId="a"
                          fill="hsl(var(--negative) / 0.55)"
                          radius={0}
                        />
                      </BarChart>
                    )}
                  </MeasuredChart>
                </div>
                <ChartLegend
                  items={[
                    {
                      swatch: "hsl(var(--positive))",
                      label: `Increased (${sentimentData[0].buyers})`,
                    },
                    { swatch: "hsl(var(--positive) / 0.55)", label: `New (${kpi.newHolderCount})` },
                    {
                      swatch: "hsl(var(--negative))",
                      label: `Decreased (${sentimentData[1].sellers})`,
                    },
                    { swatch: "hsl(var(--negative) / 0.55)", label: `Closed (${kpi.closeCount})` },
                  ]}
                />
              </div>
            </section>

            <section className="frame" aria-labelledby="flow-chart-heading">
              <h2 id="flow-chart-heading" className="frame-title">
                Reconstructed position change ($)
              </h2>
              <div className="p-3">
                <div className="h-[80px]">
                  <MeasuredChart>
                    {({ width, height }) => (
                      <BarChart
                        width={width}
                        height={height}
                        data={valueFlowData}
                        layout="vertical"
                      >
                        <XAxis type="number" hide />
                        <YAxis
                          type="category"
                          dataKey="label"
                          width={90}
                          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          cursor={{ fill: "hsl(var(--muted))" }}
                          contentStyle={TOOLTIP_STYLE}
                          labelStyle={{ color: "hsl(var(--foreground))", fontWeight: 700 }}
                          itemStyle={{ color: "hsl(var(--foreground))" }}
                          formatter={(val) => [formatValue(Number(val ?? 0)), null]}
                          separator=" : "
                        />
                        <Bar dataKey="value" radius={0} barSize={24}>
                          {valueFlowData.map((entry) => (
                            <Cell key={entry.fill + entry.value} fill={entry.fill} />
                          ))}
                        </Bar>
                      </BarChart>
                    )}
                  </MeasuredChart>
                </div>
                <ChartLegend
                  items={[
                    {
                      swatch: "hsl(var(--positive))",
                      label: `Added ${formatValue(kpi.totalValueBought)}`,
                    },
                    {
                      swatch: "hsl(var(--negative))",
                      label: `Reduced ${formatValue(kpi.totalValueSold)}`,
                    },
                  ]}
                />
              </div>
            </section>
          </div>

          <section aria-labelledby="holders-heading" className="space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <h2 id="holders-heading" className="section-title">
                {holdersTitle}
              </h2>
              <SegmentedControl
                size="sm"
                aria-label="Filter holders"
                value={holdingFilter}
                onValueChange={setHoldingFilter}
                options={HOLDING_FILTER_OPTIONS}
              />
            </div>

            {/* Mobile: row list */}
            <ul className="md:hidden border-t border-border">
              {sortedHoldings.map((h, i) => (
                <StockHolderCard key={`${h.fund}-${h.delta}-${h.value}`} h={h} rank={i + 1} />
              ))}
            </ul>

            {/* Desktop: full holders table */}
            <div className="surface hidden md:block">
              <TableFrame label={holdersTitle}>
                <table className="w-full text-sm" aria-label={holdersTitle}>
                  <thead>
                    <tr>
                      <th scope="col" className="text-right p-3 w-12">
                        #
                      </th>
                      <th scope="col" className="text-left p-3">
                        Fund
                      </th>
                      {sortableTh("portfolioPct", "Ptf %")}
                      {sortableTh("value", "Value")}
                      <th scope="col" className="text-right p-3">
                        Share Δ %
                      </th>
                      {sortableTh("deltaValue", "Position Δ $")}
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
                              <span className="badge-new">NEW</span>
                            ) : h.isClosed ? (
                              <span className="badge-closed">CLOSE</span>
                            ) : deltaNum === 0 ? (
                              <span className="badge-nochange">NO CHANGE</span>
                            ) : (
                              <span className={deltaNum > 0 ? "delta-positive" : "delta-negative"}>
                                {h.delta}
                              </span>
                            )}
                          </td>
                          <td className={`p-3 text-right font-mono ${deltaClass(h.deltaValue)}`}>
                            {formatValue(h.deltaValue)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </TableFrame>
            </div>
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
