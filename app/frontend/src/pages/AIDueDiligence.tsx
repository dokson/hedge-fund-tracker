import { useState, useMemo, useEffect } from "react";
import { useSearchParams } from "react-router";
import { toast } from "sonner";
import { IS_GH_PAGES_MODE } from "@/lib/config";
import { stockPath, ROUTES } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";
import { usePageMeta, pageTitle } from "@/hooks/usePageMeta";
import { skipToken, useQuery } from "@tanstack/react-query";
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
import { Accordion, AccordionContent, AccordionItem } from "@/components/ui/accordion";
import { Trigger as AccordionTrigger } from "@radix-ui/react-accordion";
import { PanelTitle } from "@/components/ui/PanelTitle";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { ControlBand, Field } from "@/components/ui/Field";
import { StatGrid, Stat } from "@/components/ui/Stat";
import { StatusChip } from "@/components/ui/StatusChip";
import { MetaLine, MetaSep, TextLink } from "@/components/ui/TextLink";
import { LogoPlate } from "@/components/LogoPlate";
import { toneClass } from "@/lib/tone";
import sampleDueDiligence from "@/data/sampleDueDiligence.json";
import { StockPriceChart } from "@/components/StockPriceChart";
import { ChevronDown, ClipboardCheck, TrendingDown, TrendingUp } from "lucide-react";
import { toDueDiligenceReport, type DueDiligenceReport } from "@/lib/dueDiligence";

function SentimentBadge({ sentiment }: { sentiment: string }) {
  if (!sentiment) return null;
  return (
    <StatusChip
      tone={sentiment === "Bullish" ? "positive" : sentiment === "Bearish" ? "negative" : "warning"}
    >
      {sentiment}
    </StatusChip>
  );
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
  const cls = toneClass(pct);
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
    queryFn: quarter ? () => runStockAnalysis(ticker, quarter) : skipToken,
    staleTime: 10 * 60 * 1000,
    enabled: !!ticker && validTickers.has(ticker),
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
    <div className="min-w-0 space-y-6 max-w-screen-2xl">
      <PageHeader
        title="Stock Due Diligence"
        icon={ClipboardCheck}
        description="AI-generated research on a stock’s business, valuation and risks, not investment advice."
      />

      {isReadOnly && (
        <LocalOnlyNotice
          description="Live stock research needs a local backend and your API keys. The sample below is a saved report, not a live analysis."
          sample={
            isSample && {
              label: "Sample report",
              subject: sample.ticker,
              generatedAt: sample.generated_at,
            }
          }
        />
      )}

      <ControlBand label="Analysis scope" className="grid min-w-0 gap-3 sm:flex sm:gap-x-6">
        <Field label="Ticker" htmlFor="diligence-ticker" className="[&_[role=option]]:min-h-10">
          <TickerAutocomplete
            id="diligence-ticker"
            value={inputTicker}
            onChange={setInputTicker}
            onSubmit={runDiligence}
            placeholder={isReadOnly ? "Local only" : "Enter ticker…"}
            disabled={isReadOnly}
            title={
              isReadOnly
                ? "Demo only: Stock Due Diligence is available only when running the repo locally"
                : undefined
            }
            className="min-h-10 w-full sm:w-36"
          />
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
          onClick={runDiligence}
          disabled={loading || !inputTicker || !isValidTicker || isReadOnly}
        >
          {report ? "Re-run" : "Run"}
        </Button>
      </ControlBand>

      {(loading || terminalLines.length > 0) && !report && (
        <TerminalOutput lines={terminalLines} running={loading} />
      )}

      {displayReport && !loading && (
        <div className="space-y-5">
          <Panel title="Research overview" titleId="dd-header">
            <div className="space-y-4 p-3 sm:p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex min-w-0 max-w-full items-center gap-3">
                  <LogoPlate size="lg">
                    <CompanyLogo ticker={displayReport.ticker} size={48} />
                  </LogoPlate>
                  <div className="min-w-0">
                    <TextLink
                      to={stockPath(displayReport.ticker)}
                      className="min-h-10 break-all text-2xl font-semibold leading-tight"
                      title={`View ${displayReport.ticker} analysis`}
                    >
                      {displayReport.ticker}
                    </TextLink>
                    <p
                      className="mt-1 text-sm text-muted-foreground break-words"
                      title={displayReport.company}
                    >
                      {displayReport.company}
                    </p>
                  </div>
                </div>
                <div className="flex min-w-0 flex-wrap items-start gap-4">
                  <SentimentBadge
                    sentiment={displayReport.investment_thesis?.overall_sentiment ?? ""}
                  />
                  <div className="min-w-0">
                    <div className="flex items-center gap-1">
                      <p className="metric-label">3-Month Price Target</p>
                      <span className="inline-flex [&_button]:min-h-10 [&_button]:min-w-10">
                        <InfoTooltip text="An AI-generated scenario, not a prediction or an analyst consensus. The percentage compares it with the report’s current price; neither is live market data." />
                      </span>
                    </div>
                    <p className="metric-value flex flex-wrap items-baseline gap-2 tabular-nums break-words">
                      <span>{displayReport.investment_thesis?.price_target || "N/A"}</span>
                      <PriceTargetDelta
                        priceTarget={displayReport.investment_thesis?.price_target}
                        currentPrice={displayReport.current_price}
                      />
                    </p>
                  </div>
                </div>
              </div>
              <StatGrid className="grid-cols-1 sm:grid-cols-3">
                <Stat label="Current Price" value={displayReport.current_price || "N/A"} />
                <Stat
                  label="Price on Filing Date"
                  value={displayReport.filing_date_price || "N/A"}
                />
                <Stat
                  label="Change Since Filing"
                  valueClassName="inline-flex items-center gap-1"
                  value={
                    <span
                      className={`inline-flex items-center gap-1 ${toneClass(parseFloat(displayReport.price_delta_percentage ?? ""))}`}
                    >
                      {deltaUp ? (
                        <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
                      ) : (
                        <TrendingDown className="h-3.5 w-3.5" aria-hidden="true" />
                      )}
                      {displayReport.price_delta_percentage || "N/A"}
                    </span>
                  }
                />
              </StatGrid>
            </div>
          </Panel>

          <StockPriceChart
            ticker={displayReport.ticker}
            staticData={isSample ? sample.price_history : undefined}
          />

          <Accordion
            type="multiple"
            defaultValue={sections.map((s) => s.value)}
            className="space-y-4"
          >
            {sections.map((s) => (
              <AccordionItem key={s.value} value={s.value} className="frame min-w-0">
                <PanelTitle className="frame-title block h-auto min-h-11 whitespace-normal p-0">
                  <AccordionTrigger className="group flex min-h-11 w-full items-center justify-between gap-3 px-3 py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:px-4">
                    <span className="flex min-w-0 flex-wrap items-center gap-2">
                      {s.title}
                      {s.sentiment && <SentimentBadge sentiment={s.sentiment} />}
                    </span>
                    <ChevronDown
                      aria-hidden="true"
                      className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-180"
                    />
                  </AccordionTrigger>
                </PanelTitle>
                <AccordionContent className="px-3 pb-4 pt-3 sm:px-4">
                  <p className="max-w-[70ch] whitespace-pre-line break-words text-sm leading-7 text-foreground">
                    {s.body}
                  </p>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>

          {!isSample && (
            <MetaLine className="justify-center">
              Generated by {modelUsed} <MetaSep /> {generatedAt}
            </MetaLine>
          )}
        </div>
      )}

      {!displayReport && !loading && (
        <AIEmptyState message='Select a model, enter a ticker and click "Run" to generate a comprehensive analysis.' />
      )}
    </div>
  );
}
