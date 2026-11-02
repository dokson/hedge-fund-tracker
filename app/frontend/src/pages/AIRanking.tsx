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
import { ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import { ColumnHeader } from "@/components/ui/ColumnHeader";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { ControlBand, Field } from "@/components/ui/Field";
import { StatGrid, Stat } from "@/components/ui/Stat";
import { StatusChip } from "@/components/ui/StatusChip";
import { ResponsiveTable } from "@/components/ui/ResponsiveTable";
import { signTone, toneClass } from "@/lib/tone";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { smartScoreToneClass } from "@/lib/smartScore";

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
  // Normalize the display tone to the shared 1–10 buckets; risk runs in reverse.
  const toneScore = (invert ? 100 - score : score) / 10;
  return (
    <StatusChip className={`tabular-nums ${smartScoreToneClass(toneScore)}`}>{score}</StatusChip>
  );
}

function SignedCount({ value, className = "" }: { value: number; className?: string }) {
  return (
    <span className={`tabular-nums ${toneClass(value)} ${className}`}>
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
    <li className="min-w-0 border-b border-border py-4 last:border-0">
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
      <div className="mt-1 min-w-0">
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
          <Button
            variant="secondary"
            size="sm"
            className="min-h-10"
            onClick={() => onNavigate(stockPath(s.ticker))}
          >
            Analysis
          </Button>
          <Button
            variant="secondary"
            size="sm"
            className="min-h-10"
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
    <div className="min-w-0 space-y-6 max-w-screen-2xl">
      <PageHeader
        title="Most Promising Stocks"
        icon={Sparkles}
        description="AI-generated rankings from institutional holdings and price signals, not investment advice."
      />

      {isReadOnly && (
        <LocalOnlyNotice
          description="Live AI rankings need a local backend and your API keys. The sample below is a saved report, not a live analysis."
          sample={
            isSample && {
              label: "Sample ranking",
              subject: sampleRanking.quarter,
              generatedAt: sampleRanking.generated_at,
            }
          }
        />
      )}

      <ControlBand label="Analysis scope" className="grid min-w-0 gap-3 sm:flex sm:gap-x-6">
        <Field label="Quarter">
          <p className="flex min-h-10 items-center text-sm tabular-nums">
            {quarter?.replace("Q", " Q") ?? "Not available"}
          </p>
        </Field>
        <Field label="AI model">
          <ModelSelector
            value={selectedModel}
            onChange={setSelectedModel}
            onProviderChange={setSelectedProviderId}
            className="min-h-10 w-full min-w-0 sm:w-64"
            disabled={isReadOnly}
          />
        </Field>
        <Button
          className="min-h-10 w-full sm:w-auto"
          onClick={runAnalysis}
          disabled={loading || isReadOnly}
        >
          {hasResults ? "Re-run" : "Run"}
        </Button>
      </ControlBand>

      {(loading || terminalLines.length > 0) && !hasResults && (
        <TerminalOutput lines={terminalLines} running={loading} />
      )}

      {weights && !loading && (
        <Panel
          title="AI-selected Promise Score weights"
          aside={
            modelUsed && (
              <span className="status-line font-normal">
                <span className="k">Model</span> {modelUsed}
              </span>
            )
          }
        >
          <ul className="flex flex-wrap gap-2 p-3">
            {Object.entries(weights)
              .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
              .map(([key, val]) => (
                <li key={key}>
                  <StatusChip tone={signTone(val)} className="tabular-nums">
                    {key}: {val >= 0 ? "+" : ""}
                    {(val * 100).toFixed(0)}%
                  </StatusChip>
                </li>
              ))}
          </ul>
        </Panel>
      )}

      {hasResults && !loading && (
        <Panel
          title="Stock ranking"
          titleId="ranking-results"
          className="min-w-0"
          headerClassName="h-auto min-h-11 flex-wrap gap-y-1 whitespace-normal py-2"
          aside={
            <span className="tabular-nums">
              {displayResults.length} stocks{modelUsed ? ` · ${modelUsed}` : ""}
            </span>
          }
        >
          <div className="flex items-center gap-1 px-3 py-2 text-xs text-muted-foreground">
            <p>Scores out of 100. Higher is stronger, except risk.</p>
            <span className="inline-flex shrink-0 [&_button]:min-h-10 [&_button]:min-w-10">
              <InfoTooltip text="Promise combines institutional signals with AI-selected weights. Growth measures price decline since filing, not a forecast. Momentum and low volatility rank historical prices. Risk is AI-estimated downside; lower is better. These scores are not the institutional Smart Score." />
            </span>
          </div>
          <ResponsiveTable
            label="AI ranking of the most promising stocks"
            cards={
              <ul
                className="px-3 [&_a]:min-h-10 [&_button]:min-h-10 [&_button]:min-w-10"
                aria-label="AI ranking"
              >
                {displayResults.map((s) => (
                  <RankRow key={s.ticker} s={s} onNavigate={navigate} />
                ))}
              </ul>
            }
            table={
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
                      tooltip="12-1 momentum computed from daily price history: the return from 12 months to 1 month ago, ranked across this list (1–100). Higher = stronger trend relative to the other stocks; 50 = neutral or not enough history."
                    />
                    <ColumnHeader
                      label="Low Vol"
                      align="center"
                      tooltip="Price stability computed from daily price history: annualized volatility of the last year of daily returns, ranked across this list (1–100). Higher = calmer than the other stocks; 50 = neutral or not enough history."
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
                              className="h-10 w-10 inline-flex items-center justify-center rounded-md text-muted-foreground transition-colors duration-[120ms] hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
                              <StatGrid className="grid-cols-2 lg:grid-cols-4">
                                <Stat label="High Conviction" value={s.highConvictionCount} />
                                <Stat label="Total Value" value={formatValue(s.totalValue)} />
                                <Stat label="Holders" value={s.holderCount} />
                                <Stat
                                  label="Net Buyers"
                                  value={<SignedCount value={s.netBuyers} />}
                                />
                              </StatGrid>
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
                                  className="min-h-10"
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
            }
          />
        </Panel>
      )}

      {!hasResults && !loading && (
        <AIEmptyState message='Select a model and click "Run" to generate stock rankings.' />
      )}
    </div>
  );
}
