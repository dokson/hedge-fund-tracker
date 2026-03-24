import { useState, Fragment } from "react";
import { Trash2, Eye, ChevronDown, ChevronUp } from "lucide-react";
import {
  PromiseScoreReportMetadata,
  getReport,
  deleteReport,
  formatValue,
} from "@/lib/dataService";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { TickerLink } from "@/components/EntityLinks";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";

interface PromiseScoreReportListProps {
  reports: PromiseScoreReportMetadata[];
  title: string;
  onRefresh?: () => void;
}

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

export default function PromiseScoreReportList({ reports, title, onRefresh }: PromiseScoreReportListProps) {
  const navigate = useNavigate();
  const [reportData, setReportData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [weights, setWeights] = useState<Record<string, number> | null>(null);

  const handleViewReport = async (filename: string) => {
    setLoading(true);
    try {
      const data = await getReport("promise-score", filename);
      setReportData(data);
      if (data.weights) {
        setWeights(data.weights);
      }
      setDialogOpen(true);
      setExpandedRow(null);
    } catch (err: any) {
      toast.error(`Failed to load report: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteReport = async (filename: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this report?")) return;

    try {
      await deleteReport("promise-score", filename);
      toast.success("Report deleted successfully");
      onRefresh?.();
    } catch (err: any) {
      toast.error(`Failed to delete report: ${err.message}`);
    }
  };

  const formatRelativeTime = (isoTimestamp: string): string => {
    try {
      const ts = new Date(isoTimestamp);
      const now = new Date();
      const delta = now.getTime() - ts.getTime();
      const seconds = delta / 1000;

      if (seconds < 60) return "just now";
      if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60);
        return `${minutes}m ago`;
      }
      if (seconds < 86400) {
        const hours = Math.floor(seconds / 3600);
        return `${hours}h ago`;
      }
      if (seconds < 604800) {
        const days = Math.floor(seconds / 86400);
        return `${days}d ago`;
      }
      return ts.toLocaleDateString();
    } catch {
      return isoTimestamp.slice(0, 10);
    }
  };

  const getModelName = (report: PromiseScoreReportMetadata): string => {
    if (report.model_id && report.provider_id) {
      return `${report.provider_id} - ${report.model_id}`;
    }
    return report.model_id || "Unknown Model";
  };

  if (reports.length === 0) {
    return null;
  }

  return (
    <div className="mt-6 rounded-lg border border-border bg-card">
      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          📊 {title} ({reports.length})
        </h3>
      </div>
      <div className="divide-y divide-border">
        {reports.map((report) => (
          <div
            key={report.filename}
            className="px-4 py-3 hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium">
                    {report.quarter} - Top {report.top_n}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {formatRelativeTime(report.generated_at)}
                  </span>
                  <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
                    {getModelName(report)}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleViewReport(report.filename)}
                  disabled={loading}
                >
                  <Eye className="h-3 w-3 mr-1" />
                  {loading ? "Loading..." : "View"}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => handleDeleteReport(report.filename, e)}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-[95vw] max-h-[90vh] overflow-hidden">
          <DialogHeader className="flex-shrink-0">
            <DialogTitle className="text-lg font-semibold mb-2">Most Promising Stocks Report</DialogTitle>
            {reportData && (
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
                  <div>
                    <span className="text-muted-foreground">Generated:</span>{" "}
                    <span className="text-foreground">{new Date(reportData.metadata.generated_at).toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Quarter:</span>{" "}
                    <span className="text-foreground">{reportData.metadata.quarter}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Top N:</span>{" "}
                    <span className="text-foreground">{reportData.metadata.top_n}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Model:</span>{" "}
                    <span className="text-foreground truncate max-w-[200px]" title={getModelName(reportData.metadata)}>
                      {getModelName(reportData.metadata)}
                    </span>
                  </div>
                </div>
                {weights && Object.keys(weights).length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(weights)
                      .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
                      .map(([key, val]) => (
                        <span
                          key={key}
                          className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-xs font-mono ${
                            val >= 0 ? "bg-positive/10 text-positive" : "bg-negative/10 text-negative"
                          }`}
                        >
                          {key}: {val >= 0 ? "+" : ""}
                          {(val * 100).toFixed(0)}%
                        </span>
                      ))}
                  </div>
                )}
              </div>
            )}
          </DialogHeader>
          {reportData && (
            <div className="mt-4 overflow-auto flex-1 max-h-[calc(90vh-200px)] w-full">
              <div className="space-y-4">
                <div className="rounded-lg border border-border bg-card overflow-auto w-full">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-card">
                      <tr className="border-b border-border text-xs text-muted-foreground uppercase tracking-wider">
                        <th className="text-left p-3 font-medium w-8 whitespace-nowrap">#</th>
                        <th className="text-left p-3 font-medium w-24 whitespace-nowrap">Ticker</th>
                        <th className="text-left p-3 font-medium">Company</th>
                        <th className="text-center p-3 font-medium w-16 whitespace-nowrap">Promise</th>
                        <th className="text-center p-3 font-medium w-16 whitespace-nowrap">Momentum</th>
                        <th className="text-center p-3 font-medium w-16 whitespace-nowrap">Low Vol</th>
                        <th className="text-center p-3 font-medium w-16 whitespace-nowrap">Risk</th>
                        <th className="text-right p-3 font-medium w-16 whitespace-nowrap">Holders</th>
                        <th className="text-right p-3 font-medium w-20 whitespace-nowrap">Net Buyers</th>
                        <th className="text-right p-3 font-medium w-24 whitespace-nowrap">Value</th>
                        <th className="p-3 w-8"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {(reportData as any).stocks?.slice(0, 20).map((stock: any, idx: number) => {
                        const ticker = stock.Ticker || stock.ticker;
                        const company = stock.Company || stock.company;
                        const promiseScore = Math.round(stock.Promise_Score || stock.promiseScore || 0);
                        const momentumScore = Math.round(stock.Momentum_Score || stock.momentumScore || 0);
                        const lowVolatilityScore = Math.round(stock.Low_Volatility_Score || stock.lowVolatilityScore || 0);
                        const riskScore = Math.round(stock.Risk_Score || stock.riskScore || 0);
                        const totalValue = stock.Total_Value || stock.totalValue || 0;
                        const holderCount = stock.Holder_Count || stock.holderCount || 0;
                        const netBuyers = stock.Net_Buyers || stock.netBuyers || 0;
                        const highConvictionCount = stock.High_Conviction_Count || stock.highConvictionCount || 0;
                        
                        return (
                          <Fragment key={`${ticker}-${idx}`}>
                            <tr
                              className="data-table-row cursor-pointer hover:bg-muted/20"
                              onClick={() =>
                                setExpandedRow(expandedRow === ticker ? null : ticker)
                              }
                            >
                              <td className="p-3 font-mono text-muted-foreground">{idx + 1}</td>
                              <td className="p-3">
                                <TickerLink ticker={ticker} />
                              </td>
                              <td className="p-3 text-muted-foreground max-w-[300px] overflow-hidden text-ellipsis cursor-pointer hover:text-foreground transition-colors" onClick={(e) => { e.stopPropagation(); navigate(`/stock/${ticker}`); }}>
                                <span className="block" title={company}>{company}</span>
                              </td>
                              <td className="p-3 text-center">
                                <ScoreBadge score={promiseScore} />
                              </td>
                              <td className="p-3 text-center">
                                <ScoreBadge score={momentumScore} />
                              </td>
                              <td className="p-3 text-center">
                                <ScoreBadge score={lowVolatilityScore} />
                              </td>
                              <td className="p-3 text-center">
                                <ScoreBadge score={riskScore} />
                              </td>
                              <td className="p-3 text-right font-mono">{holderCount}</td>
                              <td
                                className={`p-3 text-right font-mono ${
                                  netBuyers >= 0 ? "delta-positive" : "delta-negative"
                                }`}
                              >
                                {netBuyers >= 0 ? "+" : ""}
                                {netBuyers}
                              </td>
                              <td className="p-3 text-right font-mono">{formatValue(totalValue)}</td>
                              <td className="p-3">
                                {expandedRow === ticker ? (
                                  <ChevronUp className="h-4 w-4 text-muted-foreground" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                )}
                              </td>
                            </tr>
                            {expandedRow === ticker && (
                              <tr key={`${ticker}-detail`} className="bg-muted/30">
                                <td
                                  colSpan={11}
                                  className="px-6 py-4 text-sm text-muted-foreground border-b border-border"
                                >
                                  <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
                                    <div>
                                      <p className="text-xs uppercase tracking-wider mb-1">High Conviction</p>
                                      <p className="font-mono font-bold">{highConvictionCount}</p>
                                    </div>
                                    <div>
                                      <p className="text-xs uppercase tracking-wider mb-1">Total Value</p>
                                      <p className="font-mono font-bold">{formatValue(totalValue)}</p>
                                    </div>
                                    <div>
                                      <p className="text-xs uppercase tracking-wider mb-1">Holders</p>
                                      <p className="font-mono font-bold">{holderCount}</p>
                                    </div>
                                    <div>
                                      <p className="text-xs uppercase tracking-wider mb-1">Net Buyers</p>
                                      <p className={`font-mono font-bold ${netBuyers >= 0 ? "delta-positive" : "delta-negative"}`}>
                                        {netBuyers >= 0 ? "+" : ""}{netBuyers}
                                      </p>
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
