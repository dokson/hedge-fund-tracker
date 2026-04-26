import { useState, useMemo } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { IS_GH_PAGES_MODE } from "@/lib/config";
import { useQuery } from "@tanstack/react-query";
import {
  runStockAnalysis,
  getStocks,
  formatValue,
} from "@/lib/dataService";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { runDueDiligenceStream } from "@/lib/aiClient";
import { getModels } from "@/lib/dataService";
import TerminalOutput from "@/components/TerminalOutput";
import { Button } from "@/components/ui/button";
import TickerAutocomplete from "@/components/TickerAutocomplete";
import ModelSelector from "@/components/ModelSelector";
import { Brain, Settings, Loader2, ClipboardCheck } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import sampleDueDiligence from "@/data/sampleDueDiligence.json";

interface DueDiligenceReport {
  ticker: string;
  company: string;
  current_price: string;
  filing_date_price: string;
  price_delta_percentage: string;
  analysis: {
    business_summary: string;
    financial_health: string;
    financial_health_sentiment: string;
    valuation: string;
    valuation_sentiment: string;
    growth_vs_risks: string;
    growth_vs_risks_sentiment: string;
    institutional_sentiment: string;
    institutional_sentiment_sentiment: string;
  };
  investment_thesis: {
    overall_sentiment: string;
    thesis: string;
    price_target: string;
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

export default function AIDueDiligence() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const initialTicker = searchParams.get("ticker") || "";
  const [ticker, setTicker] = useState(initialTicker);
  const [inputTicker, setInputTicker] = useState(initialTicker);
  const { latestQuarter: quarter } = useAvailableQuarters();
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [selectedProviderId, setSelectedProviderId] = useState<string>("");
  const [report, setReport] = useState<DueDiligenceReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [progressPct, setProgressPct] = useState(0);
  const [statusMsg, setStatusMsg] = useState("");
  const [modelUsed, setModelUsed] = useState("");
  const [terminalLines, setTerminalLines] = useState<string[]>([]);
  const isReadOnly = IS_GH_PAGES_MODE;

  const { data: stocks = [] } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
    staleTime: 10 * 60 * 1000,
  });

  const validTickers = useMemo(() => new Set(stocks.map((s) => s.ticker)), [stocks]);
  const isValidTicker = validTickers.has(inputTicker);

  const { data: holdings = [] } = useQuery({
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
    const t = inputTicker.toUpperCase();
    setTicker(t);
    setLoading(true);
    setReport(null);
    setProgressPct(15);
    setTerminalLines([]);

    const models = await getModels();
    const modelDesc = models.find((m) => m.id === selectedModel)?.description || selectedModel;
    setModelUsed(modelDesc);

    try {
      setStatusMsg(`Running AI due diligence on ${t} via Python backend…`);
      const result = await runDueDiligenceStream(
        t, quarter, selectedModel || undefined, selectedProviderId || undefined,
        (line) => setTerminalLines((prev) => [...prev, line]),
      );
      setProgressPct(100);
      setStatusMsg("Complete");
      setReport(result as DueDiligenceReport);
      toast.success(`Due diligence report generated for ${t}`);
    } catch (err: any) {
      toast.error(`AI Error: ${err.message}`);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const sample = sampleDueDiligence as DueDiligenceReport & { quarter?: string; generated_by?: string };
  const displayReport: DueDiligenceReport | null = report ?? (isReadOnly ? sample : null);
  const isSample = isReadOnly && !report;

  return (
    <div className="space-y-5 max-w-7xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2"><ClipboardCheck className="h-6 w-6" /> Stock Due Diligence</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Comprehensive AI-generated analysis
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex gap-3 items-end flex-wrap">
        <div className="space-y-1">
          <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Ticker</label>
          <TickerAutocomplete
            value={inputTicker}
            onChange={setInputTicker}
            onSubmit={runDiligence}
            placeholder="Enter ticker…"
            className="w-32 bg-card border-border"
          />
        </div>
        <div className="space-y-1">
          <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Model</label>
          <ModelSelector value={selectedModel} onChange={setSelectedModel} onProviderChange={setSelectedProviderId} className="w-56" disabled={isReadOnly} />
        </div>
        <Button onClick={runDiligence} disabled={loading || !inputTicker || !isValidTicker || isReadOnly}>
          <Brain className="h-4 w-4 mr-1" /> {report ? "Re-run" : "Run"}
        </Button>
      </div>

      {isReadOnly && (
        <div className="rounded-lg border border-blue-200 bg-blue-50/50 dark:bg-blue-950/20 dark:border-blue-800 px-4 py-3">
          <p className="text-sm font-semibold text-blue-700 dark:text-blue-300 flex items-center gap-2">
            <Brain className="h-4 w-4" /> Local-Only Feature
          </p>
          <p className="text-xs text-blue-600/80 dark:text-blue-400/80 leading-relaxed mt-1">
            Stock Due Diligence requires a local Python backend to analyze data via LLMs. This live demo shows the interface only. To use this feature, run the app locally with your own API keys.
            {isSample && (
              <> Below is a sample output for <span className="font-mono font-semibold">{sample.ticker}</span> — top-ranked stock for {sample.quarter ?? "the latest quarter"}.</>
            )}
          </p>
        </div>
      )}

      {(loading || terminalLines.length > 0) && !report && (
        <TerminalOutput lines={terminalLines} running={loading} />
      )}

      {displayReport && !loading && (
        <div className="animate-slide-up space-y-5">
          <div className="rounded-lg border border-border bg-card p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <SentimentBadge sentiment={displayReport.investment_thesis.overall_sentiment} />
                <div>
                  <p className="text-sm text-muted-foreground">3-Month Price Target</p>
                  <p className="text-xl font-bold font-mono flex items-baseline gap-2">
                    <span>{displayReport.investment_thesis.price_target || "N/A"}</span>
                    {(() => {
                      const parseUsd = (v: string | undefined) => {
                        if (!v) return NaN;
                        const m = v.replace(/[,$\s]/g, "").match(/-?\d+(?:\.\d+)?/);
                        return m ? parseFloat(m[0]) : NaN;
                      };
                      const target = parseUsd(displayReport.investment_thesis.price_target);
                      const current = parseUsd(displayReport.current_price);
                      if (!isFinite(target) || !isFinite(current) || current === 0) return null;
                      const pct = ((target - current) / current) * 100;
                      const cls = pct >= 0 ? "text-green-500" : "text-red-500";
                      return (
                        <span
                          className={`text-sm font-semibold tabular-nums ${cls}`}
                          title={`${pct >= 0 ? "Upside" : "Downside"} vs current price`}
                        >
                          {pct >= 0 ? "↗" : "↘"} {Math.abs(pct).toFixed(1)}%
                        </span>
                      );
                    })()}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="font-mono font-bold text-lg">{displayReport.ticker}</p>
                <p className="text-xs text-muted-foreground">{displayReport.company}</p>
              </div>
            </div>
            <div className="flex gap-6 pt-1 border-t border-border">
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Current Price</p>
                <p className="font-mono font-bold">{displayReport.current_price || "N/A"}</p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Price on Filing Date</p>
                <p className="font-mono font-bold">{displayReport.filing_date_price || "N/A"}</p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Change Since Filing</p>
                <p className={`font-mono font-bold flex items-center gap-1 ${
                  displayReport.price_delta_percentage?.startsWith("+") ? "text-green-500" : "text-red-500"
                }`}>
                  {displayReport.price_delta_percentage?.startsWith("+") ? "📈" : "📉"}
                  {displayReport.price_delta_percentage || "N/A"}
                </p>
              </div>
            </div>
          </div>

          <Accordion
            type="multiple"
            defaultValue={["business", "financial", "valuation", "growth-risk", "institutional", "thesis"]}
            className="space-y-3"
          >
            <AccordionItem value="business" className="rounded-lg border border-border bg-card px-5">
              <AccordionTrigger className="text-sm font-semibold">Business Summary</AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {displayReport.analysis.business_summary}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="financial" className="rounded-lg border border-border bg-card px-5">
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Financial Health
                  <SentimentBadge sentiment={displayReport.analysis.financial_health_sentiment} />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {displayReport.analysis.financial_health}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="valuation" className="rounded-lg border border-border bg-card px-5">
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Valuation
                  <SentimentBadge sentiment={displayReport.analysis.valuation_sentiment} />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {displayReport.analysis.valuation}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="growth-risk" className="rounded-lg border border-border bg-card px-5">
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Growth vs. Risks
                  <SentimentBadge sentiment={displayReport.analysis.growth_vs_risks_sentiment} />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {displayReport.analysis.growth_vs_risks}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="institutional" className="rounded-lg border border-border bg-card px-5">
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Institutional Sentiment
                  <SentimentBadge sentiment={displayReport.analysis.institutional_sentiment_sentiment} />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {displayReport.analysis.institutional_sentiment}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="thesis" className="rounded-lg border border-border bg-card px-5">
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Investment Thesis
                  <SentimentBadge sentiment={displayReport.investment_thesis.overall_sentiment} />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {displayReport.investment_thesis.thesis}
              </AccordionContent>
            </AccordionItem>
          </Accordion>

          {!isSample && (
            <p className="text-xs text-muted-foreground text-center">
              Generated by {modelUsed} on {new Date().toISOString().split("T")[0]}
            </p>
          )}
        </div>
      )}

      {!displayReport && !loading && (
        <div className="rounded-lg border border-border bg-card p-12 text-center">
          <Brain className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-30" />
          <p className="text-muted-foreground">
            Select a model, enter a ticker and click "Run" to generate a comprehensive analysis.
          </p>
        </div>
      )}
    </div>
  );
}
