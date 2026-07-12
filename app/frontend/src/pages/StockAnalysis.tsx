import { useState } from "react";
import { useParams } from "react-router-dom";
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
import { stocksByIndustry, aiDiligenceFor } from "@/lib/routes";
import { getSectorStyle } from "@/lib/sectorStyle";
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
import { Brain, Loader2, Filter } from "lucide-react";
import { CompanyLogo } from "@/components/CompanyLogo";
import { StockPriceChart } from "@/components/StockPriceChart";
import { useNavigate } from "react-router-dom";
import { Progress } from "@/components/ui/progress";

/**
 * Mobile card for one holder row. Below `md` the six-column holders table is
 * replaced by these: rank + fund on the headline with the portfolio weight, a
 * three-up footer for Value / Δ% / Δ Value.
 */
function StockHolderCard({ h, rank }: { h: FundTickerHolding; rank: number }) {
  const deltaNum =
    h.delta === "NEW" ? Infinity : h.delta === "CLOSE" ? -100 : parseFloat(h.delta) || 0;
  return (
    <div className="surface p-3.5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-mono text-xs text-muted-foreground shrink-0">#{rank}</span>
          <FundCell fundName={h.fund} />
        </div>
        <span className="font-mono text-sm font-semibold shrink-0">
          {h.portfolioPct.toFixed(2)}%
        </span>
      </div>
      <div className="mt-3 pt-3 border-t border-border/60 grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="metric-label">Value</div>
          <div className="font-mono text-sm text-foreground mt-0.5">{formatValue(h.value)}</div>
        </div>
        <div>
          <div className="metric-label">Δ%</div>
          <div className="font-mono text-sm mt-0.5">
            {h.isNew ? (
              <span className="badge-new">NEW</span>
            ) : h.isClosed ? (
              <span className="badge-closed">CLOSE</span>
            ) : deltaNum === 0 ? (
              <span className="badge-nochange">—</span>
            ) : (
              <span className={deltaNum > 0 ? "delta-positive" : "delta-negative"}>{h.delta}</span>
            )}
          </div>
        </div>
        <div>
          <div className="metric-label">Δ Value</div>
          <div
            className={`font-mono text-sm mt-0.5 ${h.deltaValue > 0 ? "delta-positive" : h.deltaValue < 0 ? "delta-negative" : "text-muted-foreground"}`}
          >
            {formatValue(h.deltaValue)}
          </div>
        </div>
      </div>
    </div>
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

  // Compute KPIs from holdings
  const company = holdings[0]?.company || ticker;
  const totalValue = holdings.reduce((s, h) => s + h.value, 0);
  const totalDeltaValue = holdings.reduce((s, h) => s + h.deltaValue, 0);
  const avgPtfPct =
    holdings.length > 0 ? holdings.reduce((s, h) => s + h.portfolioPct, 0) / holdings.length : 0;
  const maxPtfPct = holdings.length > 0 ? Math.max(...holdings.map((h) => h.portfolioPct)) : 0;
  const buyerCount = holdings.filter((h) => h.isBuyer).length;
  const sellerCount = holdings.filter((h) => h.isSeller).length;
  const holderCount = holdings.filter((h) => h.isHolder).length;
  const newHolderCount = holdings.filter((h) => h.isNew).length;
  const closeCount = holdings.filter((h) => h.isClosed).length;
  const netBuyers = buyerCount - sellerCount;
  const bsRatio = sellerCount > 0 ? buyerCount / sellerCount : Infinity;

  const previousTotal = totalValue - totalDeltaValue;
  const deltaPct =
    holderCount === newHolderCount && closeCount === 0
      ? Infinity
      : previousTotal !== 0
        ? (totalDeltaValue / previousTotal) * 100
        : 0;

  const existingBuyers = buyerCount - newHolderCount;
  const existingSellers = sellerCount - closeCount;

  const sentimentData = [
    {
      label: "Buyers",
      buyers: existingBuyers,
      new: newHolderCount,
      sellers: 0,
      closed: 0,
    },
    {
      label: "Sellers",
      buyers: 0,
      new: 0,
      sellers: existingSellers,
      closed: closeCount,
    },
  ];

  // Value bought vs sold
  const totalValueBought = holdings
    .filter((h) => h.deltaValue > 0)
    .reduce((s, h) => s + h.deltaValue, 0);
  const totalValueSold = Math.abs(
    holdings.filter((h) => h.deltaValue < 0).reduce((s, h) => s + h.deltaValue, 0),
  );

  const valueFlowData = [
    { label: "Value Bought", value: totalValueBought, fill: "hsl(var(--positive))" },
    { label: "Value Sold", value: totalValueSold, fill: "hsl(var(--negative))" },
  ];

  // Sort columns
  const [sortKey, setSortKey] = useState<"shares" | "value" | "deltaValue" | "portfolioPct">(
    "portfolioPct",
  );
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [holdingFilter, setHoldingFilter] = useState<
    "all" | "buyers" | "sellers" | "new" | "closed"
  >("all");

  function toggleSort(key: typeof sortKey) {
    if (sortKey === key) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  function sortIndicator(key: typeof sortKey) {
    return sortKey === key ? (sortDir === "desc" ? " ↓" : " ↑") : "";
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
      const va = a[sortKey] as number;
      const vb = b[sortKey] as number;
      return sortDir === "desc" ? vb - va : va - vb;
    });
    return list;
  })();

  return (
    <div className="space-y-5 max-w-screen-2xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-start gap-4">
          <div className="rounded-lg border border-border bg-neutral-200 p-1.5 shadow-sm ring-1 ring-border/50 shrink-0">
            <CompanyLogo ticker={ticker} size={44} className="rounded-md" />
          </div>
          <div className="flex flex-col gap-2 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold font-mono tracking-tight leading-none">{ticker}</h1>
              <span className="text-lg font-medium text-foreground/95 leading-none tracking-tight">
                {company}
              </span>
              <StarButton active={isStarred(ticker)} onClick={() => toggleStar(ticker)} size={20} />
              {smartScore && <SmartScoreBadge score={smartScore.smartScore} />}
            </div>
            {(sector || industry) && (
              <div className="flex items-center gap-2 flex-wrap text-xs">
                {sector && (
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full border ${sectorStyle.border} ${sectorStyle.bg} ${sectorStyle.color} px-2.5 py-1 font-medium`}
                    title={`Yahoo Finance sector: ${sector}`}
                  >
                    <SectorIcon className="h-3.5 w-3.5" aria-hidden="true" />
                    {sector}
                  </span>
                )}
                {industry && (
                  <button
                    type="button"
                    onClick={() => navigate(stocksByIndustry(industry))}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card hover:bg-muted/40 hover:border-foreground/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background px-2.5 py-1 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                    title={`Browse all ${industry} stocks`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${sectorStyle.dot}`}
                      aria-hidden="true"
                    />
                    {industry}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="flex gap-3 w-full sm:w-auto">
          <Select value={quarter ?? ""} onValueChange={(v) => setSelectedQuarter(v as Quarter)}>
            <SelectTrigger className="flex-1 sm:flex-none sm:w-36 bg-card border-border">
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
            className="h-10 flex-1 sm:flex-none whitespace-nowrap"
            onClick={() => navigate(aiDiligenceFor(ticker))}
          >
            <Brain className="h-4 w-4 mr-1" /> AI Due Diligence
          </Button>
        </div>
      </div>

      {/* Smart score: independent of the selected quarter's 13F holdings, so it
          renders even for stocks no tracked fund currently holds. */}
      <SmartScorePanel score={smartScore} quarterLabel={quarter} />

      {isLoading ? (
        <div className="surface p-8">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
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
          {/* KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="kpi-card">
              <p className="metric-label">Total Held</p>
              <p className="text-xl font-bold font-mono mt-1">{formatValue(totalValue)}</p>
            </div>
            <div className="kpi-card">
              <p className="metric-label">Δ Value</p>
              <p
                className={`text-xl font-bold font-mono mt-1 ${totalDeltaValue > 0 ? "delta-positive" : totalDeltaValue < 0 ? "delta-negative" : ""}`}
              >
                {formatValue(totalDeltaValue)}
              </p>
            </div>
            <div className="kpi-card">
              <p className="metric-label">Δ %</p>
              <p
                className={`text-xl font-bold font-mono mt-1 ${deltaPct > 0 ? "delta-positive" : deltaPct < 0 ? "delta-negative" : ""}`}
              >
                {formatPct(deltaPct, true)}
              </p>
            </div>
            <div className="kpi-card">
              <p className="metric-label">Avg Ptf % / Max Ptf %</p>
              <p className="text-xl font-bold font-mono mt-1">
                {avgPtfPct.toFixed(2)}% / {maxPtfPct.toFixed(1)}%
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-7 gap-4 items-stretch">
            <div className="kpi-card">
              <p className="metric-label">Holders</p>
              <p className="text-xl font-bold font-mono mt-1">{holderCount}</p>
            </div>
            <button
              type="button"
              className={`kpi-card cursor-pointer transition-colors text-left w-full ${holdingFilter === "buyers" ? "ring-1 ring-primary" : "hover:bg-muted/50"}`}
              onClick={() => setHoldingFilter((f) => (f === "buyers" ? "all" : "buyers"))}
            >
              <p className="metric-label flex items-center gap-1">
                Buyers <Filter className="h-3 w-3" />
              </p>
              <p className="text-xl font-bold font-mono mt-1 delta-positive">{buyerCount}</p>
            </button>
            <button
              type="button"
              className={`kpi-card cursor-pointer transition-colors text-left w-full ${holdingFilter === "new" ? "ring-1 ring-primary" : "hover:bg-muted/50"}`}
              onClick={() => setHoldingFilter((f) => (f === "new" ? "all" : "new"))}
            >
              <p className="metric-label flex items-center gap-1">
                New <Filter className="h-3 w-3" />
              </p>
              <p className="text-xl font-bold font-mono mt-1 delta-positive">{newHolderCount}</p>
            </button>
            <button
              type="button"
              className={`kpi-card cursor-pointer transition-colors text-left w-full ${holdingFilter === "sellers" ? "ring-1 ring-primary" : "hover:bg-muted/50"}`}
              onClick={() => setHoldingFilter((f) => (f === "sellers" ? "all" : "sellers"))}
            >
              <p className="metric-label flex items-center gap-1">
                Sellers <Filter className="h-3 w-3" />
              </p>
              <p className="text-xl font-bold font-mono mt-1 delta-negative">{sellerCount}</p>
            </button>
            <button
              type="button"
              className={`kpi-card cursor-pointer transition-colors text-left w-full ${holdingFilter === "closed" ? "ring-1 ring-primary" : "hover:bg-muted/50"}`}
              onClick={() => setHoldingFilter((f) => (f === "closed" ? "all" : "closed"))}
            >
              <p className="metric-label flex items-center gap-1">
                Sold Out <Filter className="h-3 w-3" />
              </p>
              <p className="text-xl font-bold font-mono mt-1 delta-negative">{closeCount}</p>
            </button>
            <div className="kpi-card">
              <p className="metric-label">Net Buyers</p>
              <p
                className={`text-xl font-bold font-mono mt-1 ${netBuyers > 0 ? "delta-positive" : netBuyers < 0 ? "delta-negative" : ""}`}
              >
                {netBuyers >= 0 ? "+" : ""}
                {netBuyers}
              </p>
            </div>
            <div className="kpi-card">
              <p className="metric-label">B/S Ratio</p>
              <p className="text-xl font-bold font-mono mt-1">
                {isFinite(bsRatio) ? bsRatio.toFixed(1) + "x" : "∞"}
              </p>
            </div>
          </div>

          {/* Price history chart */}
          <StockPriceChart ticker={ticker} />

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Sentiment Chart */}
            <div className="surface p-5">
              <h3 className="section-title mb-4 text-sm">Buyers vs Sellers</h3>
              <div className="h-[80px]">
                <MeasuredChart>
                  {({ width, height }) => (
                    <BarChart width={width} height={height} data={sentimentData} layout="vertical">
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
                        cursor={{ fill: "hsl(var(--muted) / 0.3)" }}
                        content={({ active, payload }) => {
                          if (!active || !payload?.length) return null;
                          const row = payload[0]?.payload;
                          const isBuyers = row.label === "Buyers";
                          return (
                            <div
                              style={{
                                background: "hsl(var(--card))",
                                border: "1px solid hsl(var(--border))",
                                borderRadius: 6,
                                fontSize: 12,
                                color: "hsl(var(--foreground))",
                                padding: "6px 10px",
                                lineHeight: 1.6,
                              }}
                            >
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
                        radius={[0, 6, 6, 0]}
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
                        radius={[0, 6, 6, 0]}
                      />
                    </BarChart>
                  )}
                </MeasuredChart>
              </div>
            </div>

            {/* Value Bought vs Value Sold */}
            <div className="surface p-5">
              <h3 className="section-title mb-4 text-sm">Value Bought vs Value Sold</h3>
              <div className="h-[80px]">
                <MeasuredChart>
                  {({ width, height }) => (
                    <BarChart width={width} height={height} data={valueFlowData} layout="vertical">
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
                        cursor={{ fill: "hsl(var(--muted) / 0.3)" }}
                        contentStyle={{
                          background: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: 6,
                          fontSize: 12,
                          color: "hsl(var(--foreground))",
                        }}
                        labelStyle={{ color: "hsl(var(--foreground))", fontWeight: 700 }}
                        itemStyle={{ color: "hsl(var(--foreground))" }}
                        formatter={(val: number) => [formatValue(val), null]}
                        separator=" : "
                      />
                      <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={24}>
                        {valueFlowData.map((entry) => (
                          <Cell key={entry.fill + entry.value} fill={entry.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  )}
                </MeasuredChart>
              </div>
            </div>
          </div>

          {/* Fund Holdings */}
          <div>
            <h3 className="section-title text-sm md:hidden mb-3">
              Holders by Shares ({holdings.length} funds)
            </h3>
            {/* Mobile: card list */}
            <div className="md:hidden space-y-3">
              {sortedHoldings.map((h, i) => (
                <StockHolderCard key={`${h.fund}-${h.delta}-${h.value}`} h={h} rank={i + 1} />
              ))}
            </div>
          </div>

          {/* Desktop: full holders table */}
          <div className="surface overflow-hidden hidden md:block">
            <div className="p-4 border-b border-border">
              <h3 className="section-title text-sm">Holders by Shares ({holdings.length} funds)</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-muted-foreground uppercase tracking-wider">
                    <th className="text-right p-3 font-medium w-12">#</th>
                    <th className="text-left p-3 font-medium">Fund</th>
                    <th
                      className="text-right p-3 font-medium cursor-pointer hover:text-foreground"
                      onClick={() => toggleSort("portfolioPct")}
                    >
                      Ptf %{sortIndicator("portfolioPct")}
                    </th>
                    <th
                      className="text-right p-3 font-medium cursor-pointer hover:text-foreground"
                      onClick={() => toggleSort("value")}
                    >
                      Value{sortIndicator("value")}
                    </th>
                    <th className="text-right p-3 font-medium">Δ%</th>
                    <th
                      className="text-right p-3 font-medium cursor-pointer hover:text-foreground"
                      onClick={() => toggleSort("deltaValue")}
                    >
                      Δ Value{sortIndicator("deltaValue")}
                    </th>
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
                        <td
                          className={`p-3 text-right font-mono ${h.deltaValue > 0 ? "delta-positive" : h.deltaValue < 0 ? "delta-negative" : ""}`}
                        >
                          {formatValue(h.deltaValue)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
