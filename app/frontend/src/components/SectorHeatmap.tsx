import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getStocks, runQuarterAnalysis } from "@/lib/dataService";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { HoldingsTreemap } from "@/components/HoldingsTreemap";
import { Loader2, Info } from "lucide-react";

interface SectorGroup {
  name: string;
  totalValue: number;
  totalDelta: number;
  tickers: string[];
}

export default function SectorHeatmap() {
  const { latestQuarter } = useAvailableQuarters();

  const { data: stocks = [], isLoading: stocksLoading } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
  });

  const { data: quarterData = [], isLoading: quarterLoading } = useQuery({
    queryKey: ["quarterAnalysis", latestQuarter],
    queryFn: () => runQuarterAnalysis(latestQuarter!),
    enabled: !!latestQuarter,
    staleTime: 10 * 60 * 1000,
  });

  // Check if any stock has a sector assigned
  const hasSectorData = useMemo(
    () => stocks.some((s) => s.sector && s.sector.trim() !== ""),
    [stocks],
  );

  // Build sector → aggregated data
  const sectorHeatmapData = useMemo(() => {
    if (!hasSectorData || quarterData.length === 0) return [];

    const sectorTickerMap = new Map<string, string>();
    for (const s of stocks) {
      if (s.sector) sectorTickerMap.set(s.ticker, s.sector);
    }

    const groups = new Map<string, SectorGroup>();
    for (const sq of quarterData) {
      const sector = sectorTickerMap.get(sq.ticker);
      if (!sector) continue;
      const g = groups.get(sector) || { name: sector, totalValue: 0, totalDelta: 0, tickers: [] };
      g.totalValue += sq.totalValue;
      g.totalDelta += sq.totalDeltaValue;
      g.tickers.push(sq.ticker);
      groups.set(sector, g);
    }

    return [...groups.values()]
      .sort((a, b) => b.totalValue - a.totalValue)
      .map((g) => ({
        name: g.name,
        company: `${g.tickers.length} stocks`,
        value: g.totalValue,
        deltaPct: g.totalValue > 0 ? (g.totalDelta / (g.totalValue - g.totalDelta)) * 100 : 0,
        delta: g.totalDelta > 0 ? "INCREASE" : g.totalDelta < 0 ? "DECREASE" : "NO CHANGE",
      }));
  }, [hasSectorData, stocks, quarterData]);

  const isLoading = stocksLoading || quarterLoading;

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading data…
      </div>
    );
  }

  if (!hasSectorData) {
    return (
      <div className="flex items-start gap-2.5 rounded-md border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
        <Info className="h-4 w-4 mt-0.5 shrink-0 text-primary" />
        <div>
          <strong className="text-foreground">Sector heatmap is not yet active.</strong> It will
          become available once the{" "}
          <code className="text-xs bg-muted px-1 py-0.5 rounded">Sector</code> column is populated
          in <code className="text-xs bg-muted px-1 py-0.5 rounded">stocks.csv</code>.
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card p-5 space-y-3">
      <h3 className="section-title text-sm">Institutional Value by Sector</h3>
      <HoldingsTreemap data={sectorHeatmapData} onClickTicker={() => {}} height={350} />
    </div>
  );
}
