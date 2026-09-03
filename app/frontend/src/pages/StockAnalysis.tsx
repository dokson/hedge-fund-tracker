import { useMemo, useState } from "react";
import { useParams } from "react-router";
import { StarButton } from "@/components/StarButton";
import { useStarred } from "@/hooks/useStarred";
import { useQuery } from "@tanstack/react-query";
import {
  runStockAnalysis,
  fetchQuarterAnalysis,
  runQuarterAnalysis,
  formatValue,
  formatPct,
  getStocks,
  type FundTickerHolding,
} from "@/lib/dataService";
import type { SmartScoreView } from "@/lib/smartScore";
import { SmartScorePanel } from "@/components/SmartScorePanel";
import { SmartScoreBadge } from "@/components/SmartScoreBadge";
import { stocksByIndustry, aiDiligenceFor, stockPath } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";
import { usePageMeta, pageTitle } from "@/hooks/usePageMeta";
import { getSectorStyle, sectorPillStyle, SECTOR_PILL } from "@/lib/sectorStyle";
import type { Quarter } from "@/lib/quarters";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
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
import { ArrowDown, ArrowUp, Brain, ChevronDown, Loader2 } from "lucide-react";
import { CompanyLogo } from "@/components/CompanyLogo";
import { StockPriceChart } from "@/components/StockPriceChart";
import { IS_GH_PAGES_MODE } from "@/lib/config";
import { useNavigate } from "react-router";
import { Progress } from "@/components/ui/progress";

type SortKey = "shares" | "value" | "deltaValue" | "portfolioPct";
type SortDir = "asc" | "desc";
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

/** One status cell: label over value, in the shared hairline grid. */
function StatusCell({
  label,
  value,
  className = "",
}: {
  label: string;
  value: React.ReactNode;
  className?: string;
}) {
  return (
    <div className="bg-card p-3">
      <p className="metric-label">{label}</p>
      <p className={`metric-value ${className}`}>{value}</p>
    </div>
  );
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
          <span className="k">Δ%:</span>{" "}
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
          <span className="k">Δ Value:</span>{" "}
          <span className={deltaClass(h.deltaValue)}>{formatValue(h.deltaValue)}</span>
        </span>
      </div>
    </li>
  );
}

export default function StockAnalysis() {
  const { ticker = "NVDA" } = useParams();
  const navigate = useNavigate();
  const { isStarred, toggle: toggleStar } = useStarred("stock");
  const { quarters, latestQuarter } = useAvailableQuarters();
  const [selectedQuarter, setSelectedQuarter] = useState<Quarter | undefined>();
  const quarter = selectedQuarter ?? latestQuarter;
  const [progress, setProgress] = useState({ msg: "", pct: 0 });

  const { data: holdings = [], isLoading } = useQuery({
    queryKey: ["stockAnalysis", ticker, quarter],
    queryFn: () => runStockAnalysis(ticker, quarter!, (msg, pct) => setProgress({ msg, pct })),
    enabled: !!quarter,
    staleTime: 10 * 60 * 1000,
  });

  // Sector + industry come from stocks.csv (joined with sector_hierarchy inside
  // getStocks). Same in-memory cache as the rest of the app — no extra fetch.
  const { data: stocks = [] } = useQuery({ queryKey: ["stocks"], queryFn: getStocks });
  // The smart score is derived on the fly from the selected quarter's analysis
  // (same cached data the browser pages use), so it always matches the dropdown.
  const { data: quarterRows = [] } = useQuery({
    queryKey: ["quarterAnalysis", quarter],
    queryFn: async () =>
      (await fetchQuarterAnalysis(quarter!)) ?? (await runQuarterAnalysis(quarter!)),
    enabled: !!quarter,
    staleTime: 10 * 60 * 1000,
  });
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
    { label: "Value Bought", value: kpi.totalValueBought, fill: "hsl(var(--positive))" },
    { label: "Value Sold", value: kpi.totalValueSold, fill: "hsl(var(--negative))" },
  ];

  const [sortKey, setSortKey] = useState<SortKey>("portfolioPct");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [holdingFilter, setHoldingFilter] = useState<HoldingFilter>("all");

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  function SortArrow({ column }: { column: SortKey }) {
    if (sortKey !== column) return null;
    const Icon = sortDir === "desc" ? ArrowDown : ArrowUp;
    return <Icon className="ml-1 inline-block h-3 w-3 align-[-1px]" aria-hidden="true" />;
  }
  function ariaSort(key: SortKey) {
    return sortKey === key ? (sortDir === "desc" ? "descending" : "ascending") : "none";
  }

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
        <SortArrow column={keyName} />
      </button>
    </th>
  );

  return (
    <div className="space-y-5 max-w-screen-2xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-start gap-4">
          <div className="border border-border bg-card p-1.5 shrink-0">
            <CompanyLogo ticker={ticker} size={44} />
          </div>
          <div className="flex flex-col gap-2 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="page-title">
                {ticker}
                <span className="text-base font-normal text-muted-foreground">{company}</span>
              </h1>
              <StarButton active={isStarred(ticker)} onClick={() => toggleStar(ticker)} size={24} />
              {smartScore && <SmartScoreBadge score={smartScore.smartScore} />}
            </div>
            {(sector || industry) && (
              <div className="flex items-center gap-2 flex-wrap text-xs">
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
                    className="inline-flex h-7 items-center rounded-md px-2 text-xs font-medium text-muted-foreground transition-colors duration-[120ms] hover:bg-muted hover:text-foreground"
                    title={`Browse all ${industry} stocks`}
                  >
                    {industry}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="flex gap-3 w-full sm:w-auto">
          <Select value={quarter ?? ""} onValueChange={(v) => setSelectedQuarter(v as Quarter)}>
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

      {/* Smart score: independent of the selected quarter's 13F holdings, so it
          renders even for stocks no tracked fund currently holds. */}
      <SmartScorePanel score={smartScore} quarterLabel={quarter} />

      {isLoading ? (
        <div className="surface p-8">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">{progress.msg}</p>
            <Progress value={progress.pct} className="w-64" />
          </div>
        </div>
      ) : holdings.length === 0 ? (
        <div className="surface p-8 text-center text-muted-foreground">
          No fund holds {ticker} in {quarter?.replace("Q", " Q") ?? "this quarter"}. Try a different
          quarter.
        </div>
      ) : (
        <>
          <section aria-labelledby="flow-heading" className="space-y-2">
            <h2 id="flow-heading" className="section-title">
              Institutional flow, {quarter?.replace("Q", " Q")}
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border border border-border">
              <StatusCell label="Total Held" value={formatValue(kpi.totalValue)} />
              <StatusCell
                label="Δ Value"
                value={formatValue(kpi.totalDeltaValue)}
                className={deltaClass(kpi.totalDeltaValue)}
              />
              <StatusCell
                label="Δ %"
                value={formatPct(kpi.deltaPct, true)}
                className={deltaClass(kpi.deltaPct)}
              />
              <StatusCell
                label="Net Buyers"
                value={`${signed(kpi.netBuyers)} (${kpi.buyerCount}/${kpi.sellerCount})`}
                className={deltaClass(kpi.netBuyers)}
              />
            </div>
            <details className="frame group">
              <summary className="frame-title cursor-pointer list-none [&::-webkit-details-marker]:hidden">
                More flow metrics
                <ChevronDown
                  className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180"
                  aria-hidden="true"
                />
              </summary>
              <div className="m-3 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-px bg-border border border-border">
                <StatusCell label="Holders" value={kpi.holderCount} />
                <StatusCell label="Buyers" value={kpi.buyerCount} className="delta-positive" />
                <StatusCell label="New" value={kpi.newHolderCount} className="delta-positive" />
                <StatusCell label="Sellers" value={kpi.sellerCount} className="delta-negative" />
                <StatusCell label="Sold Out" value={kpi.closeCount} className="delta-negative" />
                <StatusCell
                  label="B/S Ratio"
                  value={isFinite(kpi.bsRatio) ? kpi.bsRatio.toFixed(1) + "x" : "∞"}
                />
                <StatusCell
                  label="Avg / Max Ptf %"
                  value={`${kpi.avgPtfPct.toFixed(2)}% / ${kpi.maxPtfPct.toFixed(1)}%`}
                />
              </div>
            </details>
          </section>

          {/* The static build has no backend: no chart, and no apology card either. */}
          {!IS_GH_PAGES_MODE && <StockPriceChart ticker={ticker} />}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <section className="frame" aria-labelledby="sentiment-heading">
              <h2 id="sentiment-heading" className="frame-title">
                Buyers vs Sellers
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
                Value Bought vs Value Sold
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
                      label: `Bought ${formatValue(kpi.totalValueBought)}`,
                    },
                    {
                      swatch: "hsl(var(--negative))",
                      label: `Sold ${formatValue(kpi.totalValueSold)}`,
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
                        Δ%
                      </th>
                      {sortableTh("deltaValue", "Δ Value")}
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
    </div>
  );
}
