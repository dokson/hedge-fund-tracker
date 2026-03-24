import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DueDiligenceReportMetadata } from "@/lib/dataService";

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
  metadata: {
    generated_at: string;
    quarter: string;
    model_id: string | null;
    provider_id: string | null;
  };
}

interface DueDiligenceReportModalProps {
  reportData: DueDiligenceReport | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function SentimentBadge({ sentiment }: { sentiment: string }) {
  if (!sentiment || sentiment.trim() === "") {
    return <span className="badge-neutral">N/A</span>;
  }
  const cls =
    sentiment === "Bullish"
      ? "badge-bullish"
      : sentiment === "Bearish"
      ? "badge-bearish"
      : "badge-neutral";
  return <span className={cls}>{sentiment}</span>;
}

function getModelName(report: DueDiligenceReportMetadata): string {
  if (report.model_id && report.provider_id) {
    return `${report.provider_id} - ${report.model_id}`;
  }
  return report.model_id || "Unknown Model";
}

export default function DueDiligenceReportModal({ reportData, open, onOpenChange }: DueDiligenceReportModalProps) {
  if (!reportData) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[95vw] max-h-[90vh] flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="text-lg font-semibold mb-2">Due Diligence Report</DialogTitle>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
              <div>
                <span className="text-muted-foreground">Generated:</span>{" "}
                <span className="text-foreground">{new Date(reportData.metadata.generated_at).toLocaleString()}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Ticker:</span>{" "}
                <span className="text-foreground">{reportData.metadata.ticker}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Quarter:</span>{" "}
                <span className="text-foreground">{reportData.metadata.quarter}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Model:</span>{" "}
                <span className="text-foreground truncate max-w-[200px]" title={getModelName(reportData.metadata)}>
                  {getModelName(reportData.metadata)}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Thesis:</span>{" "}
                <SentimentBadge sentiment={reportData.investment_thesis.overall_sentiment} />
              </div>
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs mt-2 pt-2 border-t border-border">
              <div>
                <p className="text-muted-foreground">3-Month Price Target</p>
                <p className="text-lg font-bold font-mono">
                  {reportData.investment_thesis.price_target || "N/A"}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Current Price</p>
                <p className="font-mono">{reportData.current_price || "N/A"}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Price on Filing Date</p>
                <p className="font-mono">{reportData.filing_date_price || "N/A"}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Change Since Filing</p>
                <p className={`font-mono ${
                  reportData.price_delta_percentage?.startsWith("+") ? "text-positive" : "text-negative"
                }`}>
                  {reportData.price_delta_percentage || "N/A"}
                </p>
              </div>
            </div>
          </div>
        </DialogHeader>
        <div className="mt-4 overflow-y-auto flex-1">

          <div className="space-y-3">
            <div className="bg-muted p-3 rounded">
              <h4 className="font-semibold mb-1">Business Summary</h4>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                {reportData.analysis.business_summary}
              </p>
            </div>
            <div className="bg-muted p-3 rounded">
              <div className="flex items-center justify-between mb-1">
                <h4 className="font-semibold">Financial Health</h4>
                <SentimentBadge sentiment={reportData.analysis.financial_health_sentiment} />
              </div>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                {reportData.analysis.financial_health}
              </p>
            </div>
            <div className="bg-muted p-3 rounded">
              <div className="flex items-center justify-between mb-1">
                <h4 className="font-semibold">Valuation</h4>
                <SentimentBadge sentiment={reportData.analysis.valuation_sentiment} />
              </div>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                {reportData.analysis.valuation}
              </p>
            </div>
            <div className="bg-muted p-3 rounded">
              <div className="flex items-center justify-between mb-1">
                <h4 className="font-semibold">Growth vs. Risks</h4>
                <SentimentBadge sentiment={reportData.analysis.growth_vs_risks_sentiment} />
              </div>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                {reportData.analysis.growth_vs_risks}
              </p>
            </div>
            <div className="bg-muted p-3 rounded">
              <div className="flex items-center justify-between mb-1">
                <h4 className="font-semibold">Institutional Sentiment</h4>
                <SentimentBadge sentiment={reportData.analysis.institutional_sentiment_sentiment} />
              </div>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                {reportData.analysis.institutional_sentiment}
              </p>
            </div>
            <div className="bg-muted p-3 rounded">
              <h4 className="font-semibold mb-1">Investment Thesis</h4>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                {reportData.investment_thesis.thesis}
              </p>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
