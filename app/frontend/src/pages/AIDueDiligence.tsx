import { useState, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AVAILABLE_QUARTERS,
  runStockAnalysis,
  getStocks,
  formatValue,
} from "@/lib/dataService";
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
import { toast } from "sonner";

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
  const [quarter] = useState(AVAILABLE_QUARTERS[AVAILABLE_QUARTERS.length - 1]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [selectedProviderId, setSelectedProviderId] = useState<string>("");
  const [report, setReport] = useState<DueDiligenceReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [progressPct, setProgressPct] = useState(0);
  const [statusMsg, setStatusMsg] = useState("");
  const [modelUsed, setModelUsed] = useState("");
  const [terminalLines, setTerminalLines] = useState<string[]>([]);

  const { data: stocks = [] } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
    staleTime: 10 * 60 * 1000,
  });

  const validTickers = useMemo(() => new Set(stocks.map((s) => s.ticker)), [stocks]);
  const isValidTicker = validTickers.has(inputTicker);

  const { data: holdings = [] } = useQuery({
    queryKey: ["stockAnalysis", ticker, quarter],
    queryFn: () => runStockAnalysis(ticker, quarter),
    staleTime: 10 * 60 * 1000,
    enabled: !!ticker && validTickers.has(ticker),
  });

  const runDiligence = async () => {
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

  return (
    <div className="space-y-5 max-w-7xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2"><ClipboardCheck className="h-6 w-6" /> Stock Due Diligence</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Comprehensive AI-generated analysis
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="icon" onClick={() => navigate("/ai-settings")}>
            <Settings className="h-4 w-4" />
          </Button>
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
          <ModelSelector value={selectedModel} onChange={setSelectedModel} onProviderChange={setSelectedProviderId} className="w-56" />
        </div>
        <Button onClick={runDiligence} disabled={loading || !inputTicker || !isValidTicker}>
          <Brain className="h-4 w-4 mr-1" /> {report ? "Re-run" : "Run"}
        </Button>
      </div>

      {(loading || terminalLines.length > 0) && !report && (
        <TerminalOutput lines={terminalLines} running={loading} />
      )}

      {report && !loading && (
        <div className="animate-slide-up space-y-5">
          <div className="rounded-lg border border-border bg-card p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <SentimentBadge sentiment={report.investment_thesis.overall_sentiment} />
                <div>
                  <p className="text-sm text-muted-foreground">3-Month Price Target</p>
                  <p className="text-xl font-bold font-mono">
                    {report.investment_thesis.price_target || "N/A"}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="font-mono font-bold text-lg">{report.ticker}</p>
                <p className="text-xs text-muted-foreground">{report.company}</p>
              </div>
            </div>
            <div className="flex gap-6 pt-1 border-t border-border">
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Current Price</p>
                <p className="font-mono font-bold">{report.current_price || "N/A"}</p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Price on Filing Date</p>
                <p className="font-mono font-bold">{report.filing_date_price || "N/A"}</p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Change Since Filing</p>
                <p className={`font-mono font-bold flex items-center gap-1 ${
                  report.price_delta_percentage?.startsWith("+") ? "text-green-500" : "text-red-500"
                }`}>
                  {report.price_delta_percentage?.startsWith("+") ? "📈" : "📉"}
                  {report.price_delta_percentage || "N/A"}
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
                {report.analysis.business_summary}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="financial" className="rounded-lg border border-border bg-card px-5">
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Financial Health
                  <SentimentBadge sentiment={report.analysis.financial_health_sentiment} />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {report.analysis.financial_health}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="valuation" className="rounded-lg border border-border bg-card px-5">
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Valuation
                  <SentimentBadge sentiment={report.analysis.valuation_sentiment} />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {report.analysis.valuation}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="growth-risk" className="rounded-lg border border-border bg-card px-5">
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Growth vs. Risks
                  <SentimentBadge sentiment={report.analysis.growth_vs_risks_sentiment} />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {report.analysis.growth_vs_risks}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="institutional" className="rounded-lg border border-border bg-card px-5">
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Institutional Sentiment
                  <SentimentBadge sentiment={report.analysis.institutional_sentiment_sentiment} />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {report.analysis.institutional_sentiment}
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="thesis" className="rounded-lg border border-border bg-card px-5">
              <AccordionTrigger className="text-sm font-semibold">
                <div className="flex items-center gap-2">
                  Investment Thesis
                  <SentimentBadge sentiment={report.investment_thesis.overall_sentiment} />
                </div>
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground leading-relaxed">
                {report.investment_thesis.thesis}
              </AccordionContent>
            </AccordionItem>
          </Accordion>

          <p className="text-xs text-muted-foreground text-center">
            Generated by {modelUsed} on {new Date().toISOString().split("T")[0]}
          </p>
        </div>
      )}

      {!report && !loading && (
        <div className="rounded-lg border border-border bg-card p-12 text-center">
          <Brain className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-30" />
          <p className="text-muted-foreground">
            Select a model, enter a ticker and click "Run" to generate a comprehensive analysis.
          </p>
          <Button variant="link" className="mt-2" onClick={() => navigate("/ai-settings")}>
            <Settings className="h-4 w-4 mr-1" /> Configure .env file
          </Button>
        </div>
      )}
    </div>
  );
}
