import { useState, useMemo, useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { IS_GH_PAGES_MODE } from "@/lib/config";
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
import { Brain, ClipboardCheck } from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import sampleDueDiligence from "@/data/sampleDueDiligence.json";
import { StockPriceChart } from "@/components/StockPriceChart";

interface DueDiligenceReport {
  ticker: string;
  company: string;
  current_price: string;
  filing_date_price: string;
  price_delta_percentage: string;
  analysis?: {
    business_summary?: string;
    financial_health?: string;
    financial_health_sentiment?: string;
    valuation?: string;
    valuation_sentiment?: string;
    growth_vs_risks?: string;
    growth_vs_risks_sentiment?: string;
    institutional_sentiment?: string;
    institutional_sentiment_sentiment?: string;
  };
  investment_thesis?: {
    overall_sentiment?: string;
    thesis?: string;
    price_target?: string;
  };
}

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
  const cls = pct >= 0 ? "text-green-500" : "text-red-500";
  return (
    <span
      className={`text-base md:text-lg font-semibold tabular-nums ${cls}`}
      title={`${pct >= 0 ? "Upside" : "Downside"} vs current price`}
    >
      {pct >= 0 ? "↗" : "↘"} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

export default function AIDueDiligence() {
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
    execute: async ({ modelId, providerId, onLog }) => {
      if (!quarter) throw new Error("No quarters available");
      const t = inputTicker.toUpperCase();
      setTicker(t);
      const result = (await runDueDiligenceStream(
        t,
        quarter,
        modelId,
        providerId,
        onLog,
      )) as DueDiligenceReport;
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

  const sample = sampleDueDiligence as DueDiligenceReport & {
    quarter?: string;
    generated_by?: string;
    generated_at?: string;
  };
  const displayReport: DueDiligenceReport | null = report ?? (isReadOnly ? sample : null);

  // When the cached report rehydrates after a page revisit (no URL param), seed
  // the ticker input so the UI matches the displayed report. One-shot: don't
  // overwrite if the user has already typed something.
  // setState-in-effect is the documented React pattern when syncing component
  // state with an external system (here: the cached run result rehydrated by
  // useAIRun). The one-shot guard prevents the cascade the linter flags.
  /* eslint-disable @eslint-react/set-state-in-effect, react-hooks/set-state-in-effect, @eslint-react/exhaustive-deps, react-hooks/exhaustive-deps */
  useEffect(() => {
    if (report && !inputTicker && !initialTicker) {
      setInputTicker(report.ticker);
      setTicker(report.ticker);
    }
  }, [report]);
  /* eslint-enable @eslint-react/set-state-in-effect, react-hooks/set-state-in-effect, @eslint-react/exhaustive-deps, react-hooks/exhaustive-deps */
  const isSample = isReadOnly && !report;

  return (
    <div className="space-y-5 max-w-screen-2xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="page-title">
            <ClipboardCheck className="h-6 w-6" /> Stock Due Diligence
          </h1>
          <p className="text-sm text-muted-foreground mt-1">Comprehensive AI-generated analysis</p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex gap-3 items-end flex-wrap">
        <div className="space-y-1">
          <span className="block text-[10px] text-muted-foreground uppercase tracking-wider">
            Ticker
          </span>
          <TickerAutocomplete
            value={inputTicker}
            onChange={setInputTicker}
            onSubmit={runDiligence}
            placeholder="Enter ticker…"
            className="w-32 bg-card border-border"
          />
        </div>
        <div className="space-y-1">
          <span className="block text-[10px] text-muted-foreground uppercase tracking-wider">
            Model
          </span>
          <ModelSelector
            value={selectedModel}
            onChange={setSelectedModel}
            onProviderChange={setSelectedProviderId}
            className="w-56"
            disabled={isReadOnly}
          />
        </div>
        <Button
          onClick={runDiligence}
          disabled={loading || !inputTicker || !isValidTicker || isReadOnly}
        >
          <Brain className="h-4 w-4 mr-1" /> {report ? "Re-run" : "Run"}
        </Button>
      </div>

      {isReadOnly && (
        <LocalOnlyNotice
          description="Stock Due Diligence requires a local Python backend to analyze data via LLMs. This live demo shows the interface only. To use this feature, run the app locally with your own API keys."
          sampleNote={
            isSample && (
              <>
                Below is a sample output for{" "}
                <span className="font-mono font-semibold">{sample.ticker}</span>
                {sample.generated_at && (
                  <>
                    {" "}
                    generated on <span className="font-mono">{sample.generated_at}</span>
                  </>
                )}
                .
              </>
            )
          }
        />
      )}

      {(loading || terminalLines.length > 0) && !report && (
        <TerminalOutput lines={terminalLines} running={loading} />
      )}

      {displayReport && !loading && (
        <div className="animate-slide-up space-y-5">
          <div className="rounded-lg border border-border bg-card p-6 space-y-5">
            <div className="flex items-start justify-between gap-6 flex-wrap">
              <div className="flex items-stretch gap-4 min-w-0">
                <div className="w-1 rounded-full bg-primary/70 shrink-0" aria-hidden="true" />
                <div className="rounded-xl border border-border bg-neutral-200 p-2 shadow-sm ring-1 ring-border/50 shrink-0 self-start">
                  <CompanyLogo ticker={displayReport.ticker} size={56} className="rounded-lg" />
                </div>
                <div className="min-w-0">
                  <Link
                    to={`/stock/${displayReport.ticker}`}
                    className="font-mono font-black tracking-tight text-5xl md:text-6xl leading-none hover:text-primary transition-colors block"
                    title={`View ${displayReport.ticker} analysis`}
                  >
                    {displayReport.ticker}
                  </Link>
                  <p
                    className="mt-2 text-lg md:text-xl font-semibold text-foreground/90 truncate"
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
                  <p className="text-xs text-muted-foreground uppercase tracking-wider">
                    3-Month Price Target
                  </p>
                  <p className="text-3xl md:text-4xl font-black font-mono flex items-baseline gap-2 justify-end mt-1">
                    <span>{displayReport.investment_thesis?.price_target || "N/A"}</span>
                    <PriceTargetDelta
                      priceTarget={displayReport.investment_thesis?.price_target}
                      currentPrice={displayReport.current_price}
                    />
                  </p>
                </div>
              </div>
            </div>
            <div className="flex gap-6 pt-1 border-t border-border">
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">
                  Current Price
                </p>
                <p className="font-mono font-bold">{displayReport.current_price || "N/A"}</p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">
                  Price on Filing Date
                </p>
                <p className="font-mono font-bold">{displayReport.filing_date_price || "N/A"}</p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">
                  Change Since Filing
                </p>
                <p
                  className={`font-mono font-bold flex items-center gap-1 ${
                    displayReport.price_delta_percentage?.startsWith("+")
                      ? "text-green-500"
                      : "text-red-500"
                  }`}
                >
                  {displayReport.price_delta_percentage?.startsWith("+") ? "📈" : "📉"}
                  {displayReport.price_delta_percentage || "N/A"}
                </p>
              </div>
            </div>
          </div>

          <StockPriceChart
            ticker={displayReport.ticker}
            staticData={isSample ? sample.price_history : undefined}
          />

          <Accordion
            type="multiple"
            defaultValue={[
              "business",
              "financial",
              "valuation",
              "growth-risk",
              "institutional",
              "thesis",
            ]}
            className="space-y-3"
          >
            <AccordionItem
              value="business"
              className="rounded-lg border border-border bg-card px-5"
            >
              <AccordionTrigger className="text-sm font-semibold">
                Business Summary
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {displayReport.analysis?.business_summary}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="financial"
              className="rounded-lg border border-border bg-card px-5"
            >
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Financial Health
                  <SentimentBadge
                    sentiment={displayReport.analysis?.financial_health_sentiment ?? ""}
                  />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {displayReport.analysis?.financial_health}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="valuation"
              className="rounded-lg border border-border bg-card px-5"
            >
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Valuation
                  <SentimentBadge sentiment={displayReport.analysis?.valuation_sentiment ?? ""} />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {displayReport.analysis?.valuation}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="growth-risk"
              className="rounded-lg border border-border bg-card px-5"
            >
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Growth vs. Risks
                  <SentimentBadge
                    sentiment={displayReport.analysis?.growth_vs_risks_sentiment ?? ""}
                  />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {displayReport.analysis?.growth_vs_risks}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="institutional"
              className="rounded-lg border border-border bg-card px-5"
            >
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Institutional Sentiment
                  <SentimentBadge
                    sentiment={displayReport.analysis?.institutional_sentiment_sentiment ?? ""}
                  />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {displayReport.analysis?.institutional_sentiment}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="thesis" className="rounded-lg border border-border bg-card px-5">
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Investment Thesis
                  <SentimentBadge
                    sentiment={displayReport.investment_thesis?.overall_sentiment ?? ""}
                  />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {displayReport.investment_thesis?.thesis}
              </AccordionContent>
            </AccordionItem>
          </Accordion>

          {!isSample && (
            <p className="text-xs text-muted-foreground text-center">
              Generated by {modelUsed} on {generatedAt}
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
