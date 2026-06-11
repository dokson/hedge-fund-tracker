import { Fragment, useState } from "react";
import { formatValue } from "@/lib/dataService";
import { stockPath, aiDiligenceFor } from "@/lib/routes";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { useAIRun } from "@/hooks/useAIRun";
import { runPromiseScoreStream } from "@/lib/aiClient";
import TerminalOutput from "@/components/TerminalOutput";
import { TickerLink, CompanyLink } from "@/components/EntityLinks";
import LocalOnlyNotice from "@/components/ai/LocalOnlyNotice";
import AIEmptyState from "@/components/ai/AIEmptyState";

import { Button } from "@/components/ui/button";
import ModelSelector from "@/components/ModelSelector";
import { Brain, ChevronDown, ChevronUp, Search, Info } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { IS_GH_PAGES_MODE } from "@/lib/config";
import sampleRanking from "@/data/sampleRanking.json";

interface RawRankedStock {
  Ticker?: string;
  ticker?: string;
  Company?: string;
  company?: string;
  Promise_Score?: number;
  promiseScore?: number;
  Momentum_Score?: number;
  momentumScore?: number;
  Low_Volatility_Score?: number;
  lowVolatilityScore?: number;
  Risk_Score?: number;
  riskScore?: number;
  Growth_Score?: number;
  growthScore?: number;
  Total_Value?: number;
  totalValue?: number;
  Holder_Count?: number;
  holderCount?: number;
  Net_Buyers?: number;
  netBuyers?: number;
  High_Conviction_Count?: number;
  highConvictionCount?: number;
}

interface RankedStock {
  rank: number;
  ticker: string;
  company: string;
  promiseScore: number;
  momentumScore: number;
  lowVolatilityScore: number;
  riskScore: number;
  growthScore: number;
  totalValue: number;
  holderCount: number;
  netBuyers: number;
  highConvictionCount: number;
  reasoning?: string;
}

type Align = "left" | "center" | "right";

function ColumnHeader({
  label,
  tooltip,
  align = "left",
  className = "",
}: {
  label: string;
  tooltip: string;
  align?: Align;
  className?: string;
}) {
  const alignClass =
    align === "center" ? "text-center" : align === "right" ? "text-right" : "text-left";
  const wrapperJustify =
    align === "center" ? "justify-center" : align === "right" ? "justify-end" : "justify-start";
  return (
    <th className={`${alignClass} p-3 font-medium ${className}`}>
      <span className={`inline-flex items-center gap-1 ${wrapperJustify}`}>
        {label}
        <Tooltip>
          <TooltipTrigger asChild>
            <Info className="h-3 w-3 text-muted-foreground/60 cursor-help" />
          </TooltipTrigger>
          <TooltipContent
            side="top"
            className="max-w-[300px] text-xs font-normal normal-case tracking-normal"
          >
            <p>{tooltip}</p>
          </TooltipContent>
        </Tooltip>
      </span>
    </th>
  );
}

function ScoreBadge({ score, invert = false }: { score: number; invert?: boolean }) {
  // Risk is the one metric where higher = worse, so `invert` mirrors the
  // thresholds: low score → green, high score → red.
  const good = invert ? score <= 20 : score >= 80;
  const mid = invert ? score <= 40 : score >= 60;
  const bg = good
    ? "bg-positive/15 text-positive"
    : mid
      ? "bg-warning/15 text-warning"
      : "bg-negative/15 text-negative";
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-bold font-mono ${bg}`}
    >
      {score}
    </span>
  );
}

/**
 * Mobile card for one ranked stock. The 12-column table can't fit a phone, so
 * below `md` each result becomes a card: rank + ticker with the hero Promise
 * score on the headline, the secondary scores + stats in a labelled grid, and
 * the two navigation actions inline (no nested expand row).
 */
function RankCard({ s, onNavigate }: { s: RankedStock; onNavigate: (path: string) => void }) {
  return (
    <div className="surface p-3.5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-mono text-xs text-muted-foreground shrink-0">#{s.rank}</span>
          <TickerLink ticker={s.ticker} />
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="metric-label">Promise</span>
          <ScoreBadge score={s.promiseScore} />
        </div>
      </div>
      <div className="mt-2">
        <CompanyLink ticker={s.ticker} company={s.company} showStar />
      </div>
      <div className="mt-3 pt-3 border-t border-border/60 grid grid-cols-3 gap-x-2 gap-y-3 text-center">
        <div>
          <div className="metric-label">Growth</div>
          <div className="mt-1">
            <ScoreBadge score={s.growthScore} />
          </div>
        </div>
        <div>
          <div className="metric-label">Momentum</div>
          <div className="mt-1">
            <ScoreBadge score={s.momentumScore} />
          </div>
        </div>
        <div>
          <div className="metric-label">Low Vol</div>
          <div className="mt-1">
            <ScoreBadge score={s.lowVolatilityScore} />
          </div>
        </div>
        <div>
          <div className="metric-label">Risk</div>
          <div className="mt-1">
            <ScoreBadge score={s.riskScore} invert />
          </div>
        </div>
        <div>
          <div className="metric-label">Holders</div>
          <div className="mt-1 font-mono text-sm">{s.holderCount}</div>
        </div>
        <div>
          <div className="metric-label">Net Buyers</div>
          <div
            className={`mt-1 font-mono text-sm ${s.netBuyers >= 0 ? "delta-positive" : "delta-negative"}`}
          >
            {s.netBuyers >= 0 ? "+" : ""}
            {s.netBuyers}
          </div>
        </div>
      </div>
      <div className="mt-3 pt-3 border-t border-border/60 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="metric-label">Total Value</div>
          <div className="mt-0.5 font-mono text-sm">{formatValue(s.totalValue)}</div>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={() => onNavigate(stockPath(s.ticker))}>
            Analysis
          </Button>
          <Button variant="outline" size="sm" onClick={() => onNavigate(aiDiligenceFor(s.ticker))}>
            <Brain className="h-3 w-3 mr-1" /> Diligence
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function AIRanking() {
  const navigate = useNavigate();
  const { latestQuarter: quarter } = useAvailableQuarters();
  const [topN] = useState(20);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [weights, setWeights] = useState<Record<string, number> | null>(null);

  const {
    selectedModel,
    setSelectedModel,
    setSelectedProviderId,
    loading,
    terminalLines,
    modelUsed,
    result: results,
    run,
  } = useAIRun<RankedStock[]>({
    execute: async ({ modelId, providerId, onLog, signal }) => {
      if (!quarter) throw new Error("No quarters available");
      const data = await runPromiseScoreStream(quarter, topN, modelId, providerId, onLog, signal);
      return (data as RawRankedStock[]).map((s, i) => ({
        rank: i + 1,
        ticker: s.Ticker ?? s.ticker ?? "",
        company: s.Company ?? s.company ?? "",
        promiseScore: Math.round(s.Promise_Score ?? s.promiseScore ?? 0),
        momentumScore: Math.round(s.Momentum_Score ?? s.momentumScore ?? 50),
        lowVolatilityScore: Math.round(s.Low_Volatility_Score ?? s.lowVolatilityScore ?? 50),
        riskScore: Math.round(s.Risk_Score ?? s.riskScore ?? 50),
        growthScore: Math.round(s.Growth_Score ?? s.growthScore ?? 0),
        totalValue: s.Total_Value ?? s.totalValue ?? 0,
        holderCount: s.Holder_Count ?? s.holderCount ?? 0,
        netBuyers: s.Net_Buyers ?? s.netBuyers ?? 0,
        highConvictionCount: s.High_Conviction_Count ?? s.highConvictionCount ?? 0,
      }));
    },
    successMessage: (ranked) => `AI ranking complete: ${ranked.length} stocks analyzed`,
    cacheKey: "ai-ranking",
  });

  const runAnalysis = async () => {
    if (!quarter) {
      toast.error("No quarters available");
      return;
    }
    setWeights(null);
    await run();
  };

  const isReadOnly = IS_GH_PAGES_MODE;
  const hasLiveResults = (results?.length ?? 0) > 0;
  const sampleResults: RankedStock[] =
    isReadOnly && !hasLiveResults
      ? (sampleRanking.stocks as RawRankedStock[]).map((s, i) => ({
          rank: i + 1,
          ticker: s.Ticker,
          company: s.Company,
          promiseScore: Math.round(s.Promise_Score ?? 0),
          momentumScore: Math.round(s.Momentum_Score ?? 50),
          lowVolatilityScore: Math.round(s.Low_Volatility_Score ?? 50),
          riskScore: Math.round(s.Risk_Score ?? 50),
          growthScore: Math.round(s.Growth_Score ?? 0),
          totalValue: s.Total_Value ?? 0,
          holderCount: s.Holder_Count ?? 0,
          netBuyers: s.Net_Buyers ?? 0,
          highConvictionCount: s.High_Conviction_Count ?? 0,
        }))
      : [];
  const displayResults: RankedStock[] = (results?.length ?? 0) > 0 ? results! : sampleResults;
  const hasResults = displayResults.length > 0;
  const isSample = isReadOnly && (results?.length ?? 0) === 0;

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <span className="eyebrow">AI ranking</span>
          <h1 className="page-title mt-1.5">
            <Search className="page-title-icon" /> Most Promising Stocks
          </h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            AI-powered discovery of the most promising stocks based on latest institutional data
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex gap-3 items-end flex-wrap">
        <div className="space-y-1 w-full sm:w-auto">
          <span className="block text-[10px] text-muted-foreground uppercase tracking-wider">
            Model
          </span>
          <ModelSelector
            value={selectedModel}
            onChange={setSelectedModel}
            onProviderChange={setSelectedProviderId}
            className="w-full sm:w-56"
            disabled={isReadOnly}
          />
        </div>
        <Button className="w-full sm:w-auto" onClick={runAnalysis} disabled={loading || isReadOnly}>
          <Brain className="h-4 w-4 mr-1" /> {hasResults ? "Re-run" : "Run"}
        </Button>
      </div>

      {isReadOnly && (
        <LocalOnlyNotice
          description="AI-powered discovery requires a local Python backend and API keys. This live demo shows the interface only. To use this feature, run the app locally with your own API keys."
          sampleNote={
            isSample && (
              <>
                Below is a sample ranking for{" "}
                <span className="font-mono">{sampleRanking.quarter}</span>
                {(sampleRanking as { generated_at?: string }).generated_at && (
                  <>
                    {" "}
                    generated on{" "}
                    <span className="font-mono">
                      {(sampleRanking as { generated_at?: string }).generated_at}
                    </span>
                  </>
                )}
                .
              </>
            )
          }
        />
      )}

      {(loading || terminalLines.length > 0) && !hasResults && (
        <TerminalOutput lines={terminalLines} running={loading} />
      )}

      {weights && !loading && (
        <div className="surface p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs text-muted-foreground uppercase tracking-wider">
              AI-Selected Promise Score Weights
            </h3>
            {modelUsed && (
              <span className="text-[10px] text-muted-foreground font-mono">
                Model: {modelUsed}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(weights)
              .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
              .map(([key, val]) => (
                <span
                  key={key}
                  className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-mono ${
                    val >= 0 ? "bg-positive/10 text-positive" : "bg-negative/10 text-negative"
                  }`}
                >
                  {key}: {val >= 0 ? "+" : ""}
                  {(val * 100).toFixed(0)}%
                </span>
              ))}
          </div>
        </div>
      )}

      {hasResults && !loading && (
        <>
          {/* Mobile: card list */}
          <div className="md:hidden space-y-3">
            {displayResults.map((s) => (
              <RankCard key={s.ticker} s={s} onNavigate={navigate} />
            ))}
          </div>

          {/* Desktop: full ranking table */}
          <div className="surface overflow-hidden hidden md:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-muted-foreground uppercase tracking-wider">
                  <th className="text-left p-3 font-medium w-12">#</th>
                  <th className="text-left p-3 font-medium">Ticker</th>
                  <th className="text-left p-3 font-medium">Company</th>
                  <ColumnHeader
                    label="Promise"
                    align="center"
                    tooltip="Aggregate AI score (1–100) combining institutional metrics (holders, net buyers, conviction, flows) using AI-selected weights for the current market regime. Higher = stronger institutional thesis."
                  />
                  <ColumnHeader
                    label="Growth"
                    align="center"
                    tooltip="Contrarian upside potential (1–100), derived from price change since the filing date. HIGHER = price has dropped (more upside potential left). 100 = price down ≥40%; 55–65 = roughly flat; ≤10 = stock has run up ≥40% (less upside left)."
                  />
                  <ColumnHeader
                    label="Momentum"
                    align="center"
                    tooltip="Strength of the stock's recent price trend and market enthusiasm (1–100). 90+ = explosive uptrend; 50–69 = moderate; <30 = strong downtrend or selling pressure."
                  />
                  <ColumnHeader
                    label="Low Vol"
                    align="center"
                    tooltip="Price stability score (1–100). Higher = more stable price action and lower historical volatility. 90+ = very low beta, minimal drawdowns; <30 = high-beta, speculative price action."
                  />
                  <ColumnHeader
                    label="Risk"
                    align="center"
                    tooltip="Potential for permanent capital loss or extreme downside (1–100). Higher = more risk. 90+ = speculative/distressed; <30 = blue-chip, predictable cash flows."
                  />
                  <ColumnHeader
                    label="Holders"
                    align="right"
                    tooltip="Number of tracked institutions currently holding this stock. Measures consensus and breadth of institutional ownership."
                  />
                  <ColumnHeader
                    label="Net Buyers"
                    align="right"
                    tooltip="Buyer_Count minus Seller_Count among tracked institutions this quarter. Positive = net institutional accumulation; negative = net distribution."
                  />
                  <ColumnHeader
                    label="Value"
                    align="right"
                    tooltip="Aggregate dollar value of this stock held across all tracked institutions at quarter-end."
                  />
                  <th className="p-3 w-10"></th>
                </tr>
              </thead>
              <tbody>
                {displayResults.map((s) => (
                  <Fragment key={s.ticker}>
                    <tr
                      key={s.ticker}
                      className="data-table-row cursor-pointer"
                      onClick={() => setExpandedRow(expandedRow === s.ticker ? null : s.ticker)}
                    >
                      <td className="p-3 font-mono text-muted-foreground">{s.rank}</td>
                      <td className="p-3">
                        <TickerLink ticker={s.ticker} />
                      </td>
                      <td className="p-3">
                        <CompanyLink
                          ticker={s.ticker}
                          company={s.company}
                          className="max-w-[180px] xl:max-w-[260px]"
                          showStar
                        />
                      </td>
                      <td className="p-3 text-center">
                        <ScoreBadge score={s.promiseScore} />
                      </td>
                      <td className="p-3 text-center">
                        <ScoreBadge score={s.growthScore} />
                      </td>
                      <td className="p-3 text-center">
                        <ScoreBadge score={s.momentumScore} />
                      </td>
                      <td className="p-3 text-center">
                        <ScoreBadge score={s.lowVolatilityScore} />
                      </td>
                      <td className="p-3 text-center">
                        <ScoreBadge score={s.riskScore} invert />
                      </td>
                      <td className="p-3 text-right font-mono">{s.holderCount}</td>
                      <td
                        className={`p-3 text-right font-mono ${
                          s.netBuyers >= 0 ? "delta-positive" : "delta-negative"
                        }`}
                      >
                        {s.netBuyers >= 0 ? "+" : ""}
                        {s.netBuyers}
                      </td>
                      <td className="p-3 text-right font-mono">{formatValue(s.totalValue)}</td>
                      <td className="p-3">
                        {expandedRow === s.ticker ? (
                          <ChevronUp className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        )}
                      </td>
                    </tr>
                    {expandedRow === s.ticker && (
                      <tr key={`${s.ticker}-detail`}>
                        <td
                          colSpan={12}
                          className="px-6 py-4 bg-muted/30 text-sm text-muted-foreground border-b border-border"
                        >
                          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                            <div>
                              <p className="text-xs uppercase tracking-wider mb-1">
                                High Conviction
                              </p>
                              <p className="font-mono font-bold">{s.highConvictionCount}</p>
                            </div>
                            <div>
                              <p className="text-xs uppercase tracking-wider mb-1">Total Value</p>
                              <p className="font-mono font-bold">{formatValue(s.totalValue)}</p>
                            </div>
                            <div>
                              <p className="text-xs uppercase tracking-wider mb-1">Holders</p>
                              <p className="font-mono font-bold">{s.holderCount}</p>
                            </div>
                            <div>
                              <p className="text-xs uppercase tracking-wider mb-1">Net Buyers</p>
                              <p
                                className={`font-mono font-bold ${s.netBuyers >= 0 ? "delta-positive" : "delta-negative"}`}
                              >
                                {s.netBuyers >= 0 ? "+" : ""}
                                {s.netBuyers}
                              </p>
                            </div>
                          </div>
                          <div className="mt-3 flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(stockPath(s.ticker));
                              }}
                            >
                              View Stock Analysis
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(aiDiligenceFor(s.ticker));
                              }}
                            >
                              <Brain className="h-3 w-3 mr-1" /> AI Due Diligence
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!hasResults && !loading && (
        <AIEmptyState message='Select a model and click "Run" to generate stock rankings.' />
      )}
    </div>
  );
}
