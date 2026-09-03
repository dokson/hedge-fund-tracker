import { useState, useMemo, useEffect } from "react";
import { useSearchParams, Link } from "react-router";
import { toast } from "sonner";
import { IS_GH_PAGES_MODE } from "@/lib/config";
import { stockPath, ROUTES } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";
import { usePageMeta, pageTitle } from "@/hooks/usePageMeta";
import { useQuery } from "@tanstack/react-query";
import { runStockAnalysis, getStocks } from "@/lib/dataService";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { useAIRun } from "@/hooks/useAIRun";
import { runDueDiligenceStream } from "@/lib/aiClient";
import TerminalOutput from "@/components/TerminalOutput";
import { CompanyLogo } from "@/components/CompanyLogo";
import { Button } from "@/components/ui/button";
import TickerAutocomplete from "@/components/TickerAutocomplete";
import ModelSelector from "@/components/ModelSelector";
import LocalOnlyNotice from "@/components/ai/LocalOnlyNotice";
import AIEmptyState from "@/components/ai/AIEmptyState";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import sampleDueDiligence from "@/data/sampleDueDiligence.json";
import { StockPriceChart } from "@/components/StockPriceChart";
import { TrendingDown, TrendingUp } from "lucide-react";
import { toDueDiligenceReport, type DueDiligenceReport } from "@/lib/dueDiligence";

function SentimentBadge({ sentiment }: { sentiment: string }) {
  if (!sentiment) return null;
  const cls =
    sentiment === "Bullish"
      ? "badge-bullish"
      : sentiment === "Bearish"
        ? "badge-bearish"
        : "badge-neutral";
  return <span className={cls}>{sentiment}</span>;
}

function PriceTargetDelta({
  priceTarget,
  currentPrice,
}: {
  priceTarget: string | undefined;
  currentPrice: string | undefined;
}) {
  const parseUsd = (v: string | undefined) => {
    if (!v) return NaN;
    const m = v.replace(/[,$\s]/g, "").match(/-?\d+(?:\.\d+)?/);
    return m ? parseFloat(m[0]) : NaN;
  };
  const target = parseUsd(priceTarget);
  const current = parseUsd(currentPrice);
  if (!isFinite(target) || !isFinite(current) || current === 0) return null;
  const pct = ((target - current) / current) * 100;
  const up = pct >= 0;
  const cls = up ? "text-positive" : "text-negative";
  const Icon = up ? TrendingUp : TrendingDown;
  return (
    <span className={`inline-flex items-center gap-1 text-[13px] tabular-nums ${cls}`}>
      <span className="sr-only">{up ? "Upside" : "Downside"} vs current price:</span>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

export default function AIDueDiligence() {
  usePageMeta({
    title: pageTitle("Stock Due Diligence"),
    description:
      "AI-generated due diligence on a single stock, grounded in the institutional flow the tracked hedge funds report to the SEC.",
    canonical: canonicalUrl(ROUTES.aiDiligence),
  });

  const [searchParams] = useSearchParams();
  const initialTicker = searchParams.get("ticker") || "";
  const [ticker, setTicker] = useState(initialTicker);
  const [inputTicker, setInputTicker] = useState(initialTicker);
  const { latestQuarter: quarter } = useAvailableQuarters();
  const [generatedAt, setGeneratedAt] = useState<string>("");
  const isReadOnly = IS_GH_PAGES_MODE;

  const {
    selectedModel,
    setSelectedModel,
    setSelectedProviderId,
    loading,
    terminalLines,
    modelUsed,
    result: report,
    run,
  } = useAIRun<DueDiligenceReport>({
    execute: async ({ modelId, providerId, onLog, signal }) => {
      if (!quarter) throw new Error("No quarters available");
      const t = inputTicker.toUpperCase();
      setTicker(t);
      const raw = await runDueDiligenceStream(t, quarter, modelId, providerId, onLog, signal);
      const result = toDueDiligenceReport(raw);
      if (!result) throw new Error("The AI returned a malformed due-diligence report — try again.");
      setGeneratedAt(new Date().toISOString().split("T")[0]);
      return result;
    },
    successMessage: (r) => `Due diligence report generated for ${r.ticker}`,
    cacheKey: "ai-diligence",
  });

  const { data: stocks = [] } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
    staleTime: 10 * 60 * 1000,
  });

  const validTickers = useMemo(() => new Set(stocks.map((s) => s.ticker)), [stocks]);
  const isValidTicker = validTickers.has(inputTicker);

  // Prefetch the per-stock holdings data into the query cache; the value is
  // consumed elsewhere via useQuery with the same key.
  useQuery({
    queryKey: ["stockAnalysis", ticker, quarter],
    queryFn: () => runStockAnalysis(ticker, quarter!),
    staleTime: 10 * 60 * 1000,
    enabled: !!ticker && !!quarter && validTickers.has(ticker),
  });

  const runDiligence = async () => {
    if (!quarter) {
      toast.error("No quarters available");
      return;
    }
    await run();
  };

  const sample = sampleDueDiligence;
  const displayReport: DueDiligenceReport | null = report ?? (isReadOnly ? sample : null);

  // When the cached report rehydrates after a page revisit (no URL param), seed
  // the ticker input so the UI matches the displayed report. One-shot: don't
  // overwrite if the user has already typed something.
  // setState-in-effect is the documented React pattern when syncing component
  // state with an external system (here: the cached run result rehydrated by
  // useAIRun). The one-shot guard prevents the cascade the linter flags.
  /* oxlint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
  useEffect(() => {
    if (report && !inputTicker && !initialTicker) {
      setInputTicker(report.ticker);
      setTicker(report.ticker);
    }
  }, [report]);
  /* oxlint-enable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
  const isSample = isReadOnly && !report;

  const sections: { value: string; title: string; body?: string; sentiment?: string }[] =
    displayReport
      ? [
          {
            value: "business",
            title: "Business Summary",
            body: displayReport.analysis?.business_summary,
          },
          {
            value: "financial",
            title: "Financial Health",
            body: displayReport.analysis?.financial_health,
            sentiment: displayReport.analysis?.financial_health_sentiment,
          },
          {
            value: "valuation",
            title: "Valuation",
            body: displayReport.analysis?.valuation,
            sentiment: displayReport.analysis?.valuation_sentiment,
          },
          {
            value: "growth-risk",
            title: "Growth vs. Risks",
            body: displayReport.analysis?.growth_vs_risks,
            sentiment: displayReport.analysis?.growth_vs_risks_sentiment,
          },
          {
            value: "institutional",
            title: "Institutional Sentiment",
            body: displayReport.analysis?.institutional_sentiment,
            sentiment: displayReport.analysis?.institutional_sentiment_sentiment,
          },
          {
            value: "thesis",
            title: "Investment Thesis",
            body: displayReport.investment_thesis?.thesis,
            sentiment: displayReport.investment_thesis?.overall_sentiment,
          },
        ]
      : [];

  const deltaUp = displayReport?.price_delta_percentage?.startsWith("+") ?? false;

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div className="space-y-1.5">
        <h1 className="page-title text-magenta">Stock Due Diligence</h1>
        <p className="text-sm text-muted-foreground">Comprehensive AI-generated analysis</p>
      </div>

      {isReadOnly && (
        <LocalOnlyNotice
          description="Stock Due Diligence requires a local Python backend to analyze data via LLMs. This live demo shows the interface only. To use this feature, run the app locally with your own API keys."
          sample={
            isSample && {
              label: "Sample report",
              subject: sample.ticker,
              generatedAt: sample.generated_at,
            }
          }
        />
      )}

      {/* Controls */}
      <div className="flex gap-3 items-end flex-wrap">
        <div className="space-y-1 w-full sm:w-auto">
          <span className="metric-label block">Ticker</span>
          <TickerAutocomplete
            value={inputTicker}
            onChange={setInputTicker}
            onSubmit={runDiligence}
            placeholder="Enter ticker…"
            className="w-full sm:w-32"
          />
        </div>
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
        <Button
          className="w-full sm:w-auto"
          onClick={runDiligence}
          disabled={loading || !inputTicker || !isValidTicker || isReadOnly}
        >
          {report ? "Re-run" : "Run"}
        </Button>
      </div>

      {(loading || terminalLines.length > 0) && !report && (
        <TerminalOutput lines={terminalLines} running={loading} />
      )}

      {displayReport && !loading && (
        <div className="space-y-5">
          <section className="frame" aria-labelledby="dd-header">
            <div className="frame-title">
              <h2 id="dd-header" className="text-magenta">
                Report header
              </h2>
            </div>
            <div className="space-y-4 p-3">
              <div className="flex items-start justify-between gap-6 flex-wrap">
                <div className="flex items-center gap-4 min-w-0">
                  <div className="rounded-sm border border-border bg-card p-1 shrink-0">
                    <CompanyLogo ticker={displayReport.ticker} size={48} />
                  </div>
                  <div className="min-w-0">
                    <Link
                      to={stockPath(displayReport.ticker)}
                      className="block text-2xl font-semibold leading-none text-foreground transition-colors duration-[120ms] hover:text-primary-text"
                      title={`View ${displayReport.ticker} analysis`}
                    >
                      {displayReport.ticker}
                    </Link>
                    <p
                      className="mt-2 text-sm text-muted-foreground truncate"
                      title={displayReport.company}
                    >
                      {displayReport.company}
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-4 shrink-0">
                  <SentimentBadge
                    sentiment={displayReport.investment_thesis?.overall_sentiment ?? ""}
                  />
                  <div className="text-right">
                    <p className="metric-label">3-Month Price Target</p>
                    <p className="metric-value flex items-baseline gap-2 justify-end">
                      <span>{displayReport.investment_thesis?.price_target || "N/A"}</span>
                      <PriceTargetDelta
                        priceTarget={displayReport.investment_thesis?.price_target}
                        currentPrice={displayReport.current_price}
                      />
                    </p>
                  </div>
                </div>
              </div>
              <dl className="grid grid-cols-1 sm:grid-cols-3 gap-px overflow-hidden rounded-sm border border-border bg-border">
                <div className="bg-card p-3">
                  <dt className="metric-label">Current Price</dt>
                  <dd className="tabular-nums">{displayReport.current_price || "N/A"}</dd>
                </div>
                <div className="bg-card p-3">
                  <dt className="metric-label">Price on Filing Date</dt>
                  <dd className="tabular-nums">{displayReport.filing_date_price || "N/A"}</dd>
                </div>
                <div className="bg-card p-3">
                  <dt className="metric-label">Change Since Filing</dt>
                  <dd
                    className={`inline-flex items-center gap-1 tabular-nums ${deltaUp ? "text-positive" : "text-negative"}`}
                  >
                    {deltaUp ? (
                      <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
                    ) : (
                      <TrendingDown className="h-3.5 w-3.5" aria-hidden="true" />
                    )}
                    {displayReport.price_delta_percentage || "N/A"}
                  </dd>
                </div>
              </dl>
            </div>
          </section>

          <StockPriceChart
            ticker={displayReport.ticker}
            staticData={isSample ? sample.price_history : undefined}
          />

          <section className="frame" aria-labelledby="dd-analysis">
            <div className="frame-title">
              <h2 id="dd-analysis" className="text-magenta">
                Analysis
              </h2>
            </div>
            <div className="px-3">
              <Accordion type="multiple" defaultValue={sections.map((s) => s.value)}>
                {sections.map((s) => (
                  <AccordionItem
                    key={s.value}
                    value={s.value}
                    className="border-b border-border/60 last:border-0"
                  >
                    <AccordionTrigger className="section-title font-normal py-3 hover:no-underline [&>svg]:text-muted-foreground">
                      <span className="flex items-center gap-3">
                        {s.title}
                        {s.sentiment && <SentimentBadge sentiment={s.sentiment} />}
                      </span>
                    </AccordionTrigger>
                    <AccordionContent className="text-sm text-muted-foreground leading-6">
                      {s.body}
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
          </section>

          {!isSample && (
            <p className="status-line text-center text-muted-foreground">
              Generated by {modelUsed} <span aria-hidden="true">·</span> {generatedAt}
            </p>
          )}
        </div>
      )}

      {!displayReport && !loading && (
        <AIEmptyState message='Select a model, enter a ticker and click "Run" to generate a comprehensive analysis.' />
      )}
    </div>
  );
}
