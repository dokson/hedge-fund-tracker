import { Fragment, useState } from "react";
import { formatValue } from "@/lib/dataService";
import { stockPath, aiDiligenceFor, ROUTES } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";
import { usePageMeta, pageTitle } from "@/hooks/usePageMeta";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { useAIRun } from "@/hooks/useAIRun";
import { runPromiseScoreStream } from "@/lib/aiClient";
import TerminalOutput from "@/components/TerminalOutput";
import { TickerLink, CompanyLink } from "@/components/EntityLinks";
import LocalOnlyNotice from "@/components/ai/LocalOnlyNotice";
import AIEmptyState from "@/components/ai/AIEmptyState";

import { Button } from "@/components/ui/button";
import ModelSelector from "@/components/ModelSelector";
import { ChevronDown, ChevronUp } from "lucide-react";
import { ColumnHeader } from "@/components/ui/ColumnHeader";
import { TableFrame } from "@/components/ui/TableFrame";
import { PanelTitle } from "@/components/ui/PanelTitle";

import { useNavigate } from "react-router";
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

function ScoreBadge({ score, invert = false }: { score: number; invert?: boolean }) {
  // Risk is the one metric where higher = worse, so `invert` mirrors the
  // thresholds: low score → green, high score → red.
  const good = invert ? score <= 20 : score >= 80;
  const mid = invert ? score <= 40 : score >= 60;
  const tone = good ? "text-positive" : mid ? "text-warning" : "text-negative";
  return <span className={`chip tabular-nums ${tone}`}>{score}</span>;
}

function SignedCount({ value, className = "" }: { value: number; className?: string }) {
  return (
    <span
      className={`tabular-nums ${value >= 0 ? "delta-positive" : "delta-negative"} ${className}`}
    >
      {value >= 0 ? "+" : ""}
      {value}
    </span>
  );
}

/**
 * Mobile row for one ranked stock. The 12-column table can't fit a phone, so
 * below `md` each result is a frame row: rank + ticker with the Promise score
 * on the headline, the secondary scores in a labelled grid, and the two
 * navigation actions inline.
 */
function RankRow({ s, onNavigate }: { s: RankedStock; onNavigate: (path: string) => void }) {
  return (
    <li className="border-b border-border/60 py-3 last:border-0">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs text-muted-foreground shrink-0 tabular-nums">#{s.rank}</span>
          <TickerLink ticker={s.ticker} />
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="metric-label">Promise</span>
          <ScoreBadge score={s.promiseScore} />
        </div>
      </div>
      <div className="mt-1">
        <CompanyLink ticker={s.ticker} company={s.company} showStar />
      </div>
      <dl className="mt-3 grid grid-cols-3 gap-x-2 gap-y-3 text-center">
        <div>
          <dt className="metric-label">Growth</dt>
          <dd className="mt-1">
            <ScoreBadge score={s.growthScore} />
          </dd>
        </div>
        <div>
          <dt className="metric-label">Momentum</dt>
          <dd className="mt-1">
            <ScoreBadge score={s.momentumScore} />
          </dd>
        </div>
        <div>
          <dt className="metric-label">Low Vol</dt>
          <dd className="mt-1">
            <ScoreBadge score={s.lowVolatilityScore} />
          </dd>
        </div>
        <div>
          <dt className="metric-label">Risk</dt>
          <dd className="mt-1">
            <ScoreBadge score={s.riskScore} invert />
          </dd>
        </div>
        <div>
          <dt className="metric-label">Holders</dt>
          <dd className="mt-1 text-[13px] tabular-nums">{s.holderCount}</dd>
        </div>
        <div>
          <dt className="metric-label">Net Buyers</dt>
          <dd className="mt-1 text-sm">
            <SignedCount value={s.netBuyers} />
          </dd>
        </div>
      </dl>
      <div className="mt-3 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <span className="metric-label">Total Value</span>
          <div className="text-[13px] tabular-nums">{formatValue(s.totalValue)}</div>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="secondary" size="sm" onClick={() => onNavigate(stockPath(s.ticker))}>
            Analysis
          </Button>
          <Button
            variant="secondary"
            size="sm"
            className="text-magenta"
            onClick={() => onNavigate(aiDiligenceFor(s.ticker))}
          >
            Diligence
          </Button>
        </div>
      </div>
    </li>
  );
}

export default function AIRanking() {
  usePageMeta({
    title: pageTitle("Most Promising Stocks"),
    description:
      "An AI-weighted Promise Score ranking the stocks with the strongest institutional thesis: holders, net buyers, conviction and flows.",
    canonical: canonicalUrl(ROUTES.aiRanking),
  });

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
      // Field-level defense lives in the `??` fallbacks below; here we only
      // drop non-object elements so a null in the AI response can't throw.
      const rows = data.filter((s): s is RawRankedStock => typeof s === "object" && s !== null);
      return rows.map((s, i) => ({
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
      ? sampleRanking.stocks.map((s, i) => ({
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
  const displayResults: RankedStock[] = results && results.length > 0 ? results : sampleResults;
  const hasResults = displayResults.length > 0;
  const isSample = isReadOnly && (results?.length ?? 0) === 0;

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div className="space-y-1.5">
        <h1 className="page-title text-magenta">Most Promising Stocks</h1>
        <p className="text-sm text-muted-foreground">
          AI-powered discovery of the most promising stocks based on latest institutional data
        </p>
      </div>

      {isReadOnly && (
        <LocalOnlyNotice
          description="AI-powered discovery requires a local Python backend and API keys. This live demo shows the interface only. To use this feature, run the app locally with your own API keys."
          sample={
            isSample && {
              label: "Sample ranking",
              subject: sampleRanking.quarter,
              generatedAt: sampleRanking.generated_at,
            }
          }
        />
      )}

      {/* Controls */}
      <div className="flex gap-3 items-end flex-wrap">
        <div className="space-y-1 w-full sm:w-auto">
          <span className="metric-label block">Model</span>
          <ModelSelector
            value={selectedModel}
            onChange={setSelectedModel}
            onProviderChange={setSelectedProviderId}
            className="w-full sm:w-56"
            disabled={isReadOnly}
          />
        </div>
        <Button className="w-full sm:w-auto" onClick={runAnalysis} disabled={loading || isReadOnly}>
          {hasResults ? "Re-run" : "Run"}
        </Button>
      </div>

      {(loading || terminalLines.length > 0) && !hasResults && (
        <TerminalOutput lines={terminalLines} running={loading} />
      )}

      {weights && !loading && (
        <div className="frame">
          <div className="frame-title">
            <PanelTitle className="text-magenta">AI-selected Promise Score weights</PanelTitle>
            {modelUsed && (
              <span className="status-line font-normal">
                <span className="k">Model</span> {modelUsed}
              </span>
            )}
          </div>
          <ul className="flex flex-wrap gap-2 p-3">
            {Object.entries(weights)
              .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
              .map(([key, val]) => (
                <li
                  key={key}
                  className={`chip tabular-nums ${val >= 0 ? "text-positive" : "text-negative"}`}
                >
                  {key}: {val >= 0 ? "+" : ""}
                  {(val * 100).toFixed(0)}%
                </li>
              ))}
          </ul>
        </div>
      )}

      {hasResults && !loading && (
        <>
          {/* Mobile: frame rows */}
          <ul className="md:hidden frame px-3" aria-label="AI ranking">
            {displayResults.map((s) => (
              <RankRow key={s.ticker} s={s} onNavigate={navigate} />
            ))}
          </ul>

          {/* Desktop: full ranking table */}
          <div className="frame hidden md:block">
            <TableFrame label="AI ranking of the most promising stocks">
              <table
                className="w-full text-sm"
                aria-label="AI ranking of the most promising stocks"
              >
                <thead>
                  <tr className="text-xs">
                    <th scope="col" className="text-left p-3 w-12">
                      #
                    </th>
                    <th scope="col" className="text-left p-3">
                      Ticker
                    </th>
                    <th scope="col" className="text-left p-3">
                      Company
                    </th>
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
                    <th scope="col" className="p-3 w-10">
                      <span className="sr-only">Details</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {displayResults.map((s) => {
                    const expanded = expandedRow === s.ticker;
                    return (
                      <Fragment key={s.ticker}>
                        <tr
                          className="data-table-row cursor-pointer"
                          onClick={() => setExpandedRow(expanded ? null : s.ticker)}
                        >
                          <td className="p-3 text-muted-foreground tabular-nums">{s.rank}</td>
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
                          <td className="p-3 text-right tabular-nums">{s.holderCount}</td>
                          <td className="p-3 text-right">
                            <SignedCount value={s.netBuyers} />
                          </td>
                          <td className="p-3 text-right tabular-nums">
                            {formatValue(s.totalValue)}
                          </td>
                          <td className="p-1">
                            <button
                              type="button"
                              aria-expanded={expanded}
                              aria-label={`${expanded ? "Hide" : "Show"} details for ${s.ticker}`}
                              className="h-7 w-7 inline-flex items-center justify-center rounded-md text-muted-foreground transition-colors duration-[120ms] hover:bg-muted hover:text-foreground"
                              onClick={(e) => {
                                e.stopPropagation();
                                setExpandedRow(expanded ? null : s.ticker);
                              }}
                            >
                              {expanded ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </button>
                          </td>
                        </tr>
                        {expanded && (
                          <tr>
                            <td
                              colSpan={12}
                              className="px-6 py-4 bg-muted/40 text-[13px] text-muted-foreground border-b border-border/60"
                            >
                              <dl className="grid grid-cols-2 lg:grid-cols-4 gap-px rounded-sm border border-border bg-border overflow-hidden">
                                <div className="bg-card p-3">
                                  <dt className="metric-label">High Conviction</dt>
                                  <dd className="text-foreground tabular-nums">
                                    {s.highConvictionCount}
                                  </dd>
                                </div>
                                <div className="bg-card p-3">
                                  <dt className="metric-label">Total Value</dt>
                                  <dd className="text-foreground tabular-nums">
                                    {formatValue(s.totalValue)}
                                  </dd>
                                </div>
                                <div className="bg-card p-3">
                                  <dt className="metric-label">Holders</dt>
                                  <dd className="text-foreground tabular-nums">{s.holderCount}</dd>
                                </div>
                                <div className="bg-card p-3">
                                  <dt className="metric-label">Net Buyers</dt>
                                  <dd>
                                    <SignedCount value={s.netBuyers} />
                                  </dd>
                                </div>
                              </dl>
                              <div className="mt-3 flex gap-2">
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    void navigate(stockPath(s.ticker));
                                  }}
                                >
                                  View Stock Analysis
                                </Button>
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  className="text-magenta"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    void navigate(aiDiligenceFor(s.ticker));
                                  }}
                                >
                                  AI Due Diligence
                                </Button>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </TableFrame>
          </div>
        </>
      )}

      {!hasResults && !loading && (
        <AIEmptyState message='Select a model and click "Run" to generate stock rankings.' />
      )}
    </div>
  );
}
