import { useState } from "react";
import { Trash2, Eye } from "lucide-react";
import {
  DueDiligenceReportMetadata,
  getReport,
  deleteReport,
} from "@/lib/dataService";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import DueDiligenceReportModal from "./DueDiligenceReportModal";

interface DueDiligenceReportListProps {
  reports: DueDiligenceReportMetadata[];
  title: string;
  onRefresh?: () => void;
}

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
    ticker: string;
  };
}

export default function DueDiligenceReportList({ reports, title, onRefresh }: DueDiligenceReportListProps) {
  const [reportData, setReportData] = useState<DueDiligenceReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleViewReport = async (filename: string) => {
    setLoading(true);
    try {
      const data = await getReport("due-diligence", filename);
      setReportData(data as DueDiligenceReport);
      setDialogOpen(true);
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
      await deleteReport("due-diligence", filename);
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

  const getModelName = (report: DueDiligenceReportMetadata): string => {
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
          📋 {title} ({reports.length})
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
                    {report.ticker} - {report.quarter}
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

      <DueDiligenceReportModal
        reportData={reportData}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />
    </div>
  );
}
