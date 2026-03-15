import { useState } from "react";
import {
  AVAILABLE_QUARTERS,
  formatValue,
} from "@/lib/dataService";
import { runPromiseScoreStream } from "@/lib/aiClient";
import { getModels } from "@/lib/dataService";
import TerminalOutput from "@/components/TerminalOutput";
import { TickerLink } from "@/components/EntityLinks";

import { Button } from "@/components/ui/button";
import ModelSelector from "@/components/ModelSelector";
import { Brain, ChevronDown, ChevronUp, Settings, Search } from "lucide-react";

import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

interface RankedStock {
  rank: number;
  ticker: string;
  company: string;
  promiseScore: number;
  momentumScore: number;
  lowVolatilityScore: number;
  riskScore: number;
  totalValue: number;
  holderCount: number;
  netBuyers: number;
  highConvictionCount: number;
  reasoning?: string;
}

function ScoreBadge({ score }: { score: number }) {
  const bg =
    score >= 80
      ? "bg-positive/15 text-positive"
      : score >= 60
      ? "bg-warning/15 text-warning"
      : "bg-negative/15 text-negative";
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-bold font-mono ${bg}`}>
      {score}
    </span>
  );
}

export default function AIRanking() {
  const navigate = useNavigate();
  const quarter = AVAILABLE_QUARTERS[AVAILABLE_QUARTERS.length - 1];
  const [topN, setTopN] = useState(20);
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [results, setResults] = useState<RankedStock[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [progressPct, setProgressPct] = useState(0);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [weights, setWeights] = useState<Record<string, number> | null>(null);
  const [modelUsed, setModelUsed] = useState("");
  const [terminalLines, setTerminalLines] = useState<string[]>([]);

  const runAnalysis = async () => {
    setLoading(true);
    setResults([]);
    setWeights(null);
    setTerminalLines([]);

    try {
      const models = await getModels();
      const modelDesc = models.find((m) => m.id === selectedModel)?.description || selectedModel;
      setModelUsed(modelDesc);
      setStatusMsg("Running AI Promise Score analysis…");
      setProgressPct(15);

      const data = await runPromiseScoreStream(
        quarter, topN, selectedModel || undefined, selectedProviderId || undefined,
        (line) => setTerminalLines((prev) => [...prev, line]),
      );

      setProgressPct(95);
      setStatusMsg("Combining results…");

      const ranked: RankedStock[] = data.map((s: any, i: number) => ({
        rank: i + 1,
        ticker: s.Ticker ?? s.ticker ?? "",
        company: s.Company ?? s.company ?? "",
        promiseScore: Math.round(s.Promise_Score ?? s.promiseScore ?? 0),
        momentumScore: Math.round(s.Momentum_Score ?? s.momentumScore ?? 50),
        lowVolatilityScore: Math.round(s.Low_Volatility_Score ?? s.lowVolatilityScore ?? 50),
        riskScore: Math.round(s.Risk_Score ?? s.riskScore ?? 50),
        totalValue: s.Total_Value ?? s.totalValue ?? 0,
        holderCount: s.Holder_Count ?? s.holderCount ?? 0,
        netBuyers: s.Net_Buyers ?? s.netBuyers ?? 0,
        highConvictionCount: s.High_Conviction_Count ?? s.highConvictionCount ?? 0,
      }));

      setResults(ranked);
      setProgressPct(100);
      setStatusMsg("Complete");
      toast.success(`AI ranking complete: ${ranked.length} stocks analyzed`);
    } catch (err: any) {
      toast.error(`AI Error: ${err.message}`);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const hasResults = results.length > 0;

  return (
    <div className="space-y-5 max-w-7xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2"><Search className="h-6 w-6" /> Most Promising Stocks</h1>
          <p className="text-sm text-muted-foreground mt-1">
            AI-powered discovery of the most promising stocks based on latest institutional data
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
          <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Model</label>
          <ModelSelector value={selectedModel} onChange={setSelectedModel} onProviderChange={setSelectedProviderId} className="w-56" />
        </div>
        <Button onClick={runAnalysis} disabled={loading}>
          <Brain className="h-4 w-4 mr-1" /> {hasResults ? "Re-run" : "Run"}
        </Button>
      </div>

      {(loading || terminalLines.length > 0) && !hasResults && (
        <TerminalOutput lines={terminalLines} running={loading} />
      )}

      {weights && !loading && (
        <div className="rounded-lg border border-border bg-card p-4">
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
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-muted-foreground uppercase tracking-wider">
                <th className="text-left p-3 font-medium w-12">#</th>
                <th className="text-left p-3 font-medium">Ticker</th>
                <th className="text-left p-3 font-medium">Company</th>
                <th className="text-center p-3 font-medium">Promise</th>
                <th className="text-center p-3 font-medium">Momentum</th>
                <th className="text-center p-3 font-medium">Low Vol</th>
                <th className="text-center p-3 font-medium">Risk</th>
                <th className="text-right p-3 font-medium">Holders</th>
                <th className="text-right p-3 font-medium">Net Buyers</th>
                <th className="text-right p-3 font-medium">Value</th>
                <th className="p-3 w-10"></th>
              </tr>
            </thead>
            <tbody>
              {results.map((s) => (
                <>
                  <tr
                    key={s.ticker}
                    className="data-table-row cursor-pointer"
                    onClick={() =>
                      setExpandedRow(expandedRow === s.ticker ? null : s.ticker)
                    }
                  >
                    <td className="p-3 font-mono text-muted-foreground">{s.rank}</td>
                    <td className="p-3">
                      <TickerLink ticker={s.ticker} />
                    </td>
                    <td className="p-3 text-muted-foreground truncate max-w-[200px] cursor-pointer hover:text-foreground transition-colors" onClick={() => navigate(`/stock/${s.ticker}`)}>
                      {s.company}
                    </td>
                    <td className="p-3 text-center">
                      <ScoreBadge score={s.promiseScore} />
                    </td>
                    <td className="p-3 text-center">
                      <ScoreBadge score={s.momentumScore} />
                    </td>
                    <td className="p-3 text-center">
                      <ScoreBadge score={s.lowVolatilityScore} />
                    </td>
                    <td className="p-3 text-center">
                      <ScoreBadge score={s.riskScore} />
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
                        colSpan={11}
                        className="px-6 py-4 bg-muted/30 text-sm text-muted-foreground border-b border-border"
                      >
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                          <div>
                            <p className="text-xs uppercase tracking-wider mb-1">High Conviction</p>
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
                            <p className={`font-mono font-bold ${s.netBuyers >= 0 ? "delta-positive" : "delta-negative"}`}>
                              {s.netBuyers >= 0 ? "+" : ""}{s.netBuyers}
                            </p>
                          </div>
                        </div>
                        <div className="mt-3 flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => { e.stopPropagation(); navigate(`/stock/${s.ticker}`); }}
                          >
                            View Stock Analysis
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => { e.stopPropagation(); navigate(`/ai-diligence?ticker=${s.ticker}`); }}
                          >
                            <Brain className="h-3 w-3 mr-1" /> AI Due Diligence
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!hasResults && !loading && (
        <div className="rounded-lg border border-border bg-card p-12 text-center">
          <Brain className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-30" />
          <p className="text-muted-foreground">
            Select a model and click "Run" to generate stock rankings.
          </p>
          <Button variant="link" className="mt-2" onClick={() => navigate("/ai-settings")}>
            <Settings className="h-4 w-4 mr-1" /> Configure .env file
          </Button>
        </div>
      )}
    </div>
  );
}
