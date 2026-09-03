import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { Loader2 } from "lucide-react";
import { HoldingsTreemap } from "@/components/HoldingsTreemap";
import { Button } from "@/components/ui/button";
import { PanelTitle } from "@/components/ui/PanelTitle";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { getQuarterFundList, getStocks, runQuarterAnalysis } from "@/lib/dataService";
import { STRATEGY_BY_ID } from "@/lib/strategies";
import { selectSmartScoreScreen, selectStrategyScreen } from "@/lib/strategyScreen";
import { seriesColor } from "@/lib/seriesColors";
import { stockPath } from "@/lib/routes";

interface TreemapItem {
  name: string;
  company: string;
  value: number;
  deltaPct: number;
  delta: string;
}

/**
 * Drill-down for the strategy currently focused on the Performance page:
 * reconstructs its screen for a chosen quarter (client-side, composition only)
 * and shows its weight breakdown by stock and by sector, reusing the site-wide
 * HoldingsTreemap (sized by weight, colored by quarter-over-quarter change).
 */
export default function CompositionPanel({ strategyId }: { strategyId: string }) {
  const navigate = useNavigate();
  const { quarters, latestQuarter } = useAvailableQuarters();
  const [selectedQuarter, setSelectedQuarter] = useState<string | undefined>();
  const quarter = selectedQuarter ?? latestQuarter;
  const def = STRATEGY_BY_ID[strategyId];

  const { data: analysis = [], isLoading } = useQuery({
    queryKey: ["quarterAnalysis", quarter, "all"],
    queryFn: () => runQuarterAnalysis(quarter!),
    enabled: !!quarter,
    staleTime: 10 * 60 * 1000,
  });
  const { data: stocks = [] } = useQuery({ queryKey: ["stocks"], queryFn: getStocks });
  const { data: fundList = [] } = useQuery({
    queryKey: ["quarterFundList", quarter],
    queryFn: () => getQuarterFundList(quarter!),
    enabled: !!quarter,
    staleTime: Infinity,
  });

  const minHolders = Math.max(1, Math.ceil(fundList.length / (def?.minHoldersDivisor ?? 10)));
  const sectorOf = useMemo(() => {
    const map = new Map(stocks.map((s) => [s.ticker, s.sector]));
    return (ticker: string) => map.get(ticker) || "Unknown";
  }, [stocks]);

  const { stockItems, sectorItems, tickersBySector } = useMemo(() => {
    const holdings =
      strategyId === "smart_score"
        ? selectSmartScoreScreen(analysis)
        : def
          ? selectStrategyScreen(analysis, def, minHolders)
          : [];
    const stockItems: TreemapItem[] = holdings.map((h) => ({
      name: h.ticker,
      company: h.company,
      value: h.weight * 100,
      deltaPct: h.deltaPct,
      delta: h.isNew ? "NEW" : "",
    }));

    // Aggregate the screen by sector: weight + weighted Δ + holding count.
    const groups = new Map<string, { weight: number; count: number; wDelta: number }>();
    const tickersBySector = new Map<string, Set<string>>();
    for (const h of holdings) {
      const sector = sectorOf(h.ticker);
      const g = groups.get(sector) || { weight: 0, count: 0, wDelta: 0 };
      g.weight += h.weight;
      g.count += 1;
      g.wDelta += h.weight * h.deltaPct;
      groups.set(sector, g);
      const members = tickersBySector.get(sector) ?? new Set<string>();
      members.add(h.ticker);
      tickersBySector.set(sector, members);
    }
    const sectorItems: TreemapItem[] = [...groups.entries()]
      .sort((a, b) => b[1].weight - a[1].weight)
      .map(([sector, g]) => {
        const deltaPct = g.weight > 0 ? g.wDelta / g.weight : 0;
        return {
          name: sector,
          company: `${g.count} ${g.count === 1 ? "stock" : "stocks"}`,
          value: g.weight * 100,
          deltaPct,
          delta: deltaPct > 0 ? "INCREASE" : deltaPct < 0 ? "DECREASE" : "NO CHANGE",
        };
      });
    return { stockItems, sectorItems, tickersBySector };
  }, [analysis, def, minHolders, sectorOf, strategyId]);

  // Selecting a sector filters the stock treemap visually. Derived, not stored:
  // a quarter or strategy change can drop the sector from the screen entirely.
  const [pickedSector, setPickedSector] = useState<string | null>(null);
  const selectedSector = pickedSector && tickersBySector.has(pickedSector) ? pickedSector : null;
  const highlightNames = selectedSector ? tickersBySector.get(selectedSector) : null;

  useEffect(() => {
    if (!selectedSector) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPickedSector(null);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [selectedSector]);

  const Icon = def?.icon;
  const label = def?.label ?? strategyId;

  return (
    <div className="frame">
      <div className="frame-title">
        <PanelTitle className="flex items-center gap-1.5">
          {Icon && <Icon className="h-4 w-4" style={{ color: seriesColor(strategyId) }} />}
          Composition · {label}
        </PanelTitle>
        <span className="ml-auto flex items-center gap-2">
          {selectedSector && (
            <Button variant="ghost" size="sm" onClick={() => setPickedSector(null)}>
              Clear {selectedSector}
            </Button>
          )}
          <Select value={quarter ?? ""} onValueChange={setSelectedQuarter}>
            <SelectTrigger aria-label="Quarter" className="h-7 w-32 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[...quarters].reverse().map((q) => (
                <SelectItem key={q} value={q}>
                  {q.replace("Q", " Q")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </span>
      </div>

      <div className="p-3">
        {isLoading ? (
          <div className="h-[260px] flex items-center justify-center text-muted-foreground gap-2 text-sm">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading composition…
          </div>
        ) : stockItems.length === 0 ? (
          <div className="h-[260px] flex items-center justify-center text-sm text-muted-foreground">
            No holdings for this strategy in {quarter}.
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <div className="metric-label mb-2">
                By stock ({stockItems.length})
                {selectedSector && (
                  <span className="text-muted-foreground"> · {selectedSector}</span>
                )}
              </div>
              <HoldingsTreemap
                data={stockItems}
                displayMode="pct"
                height={300}
                highlightNames={highlightNames}
                onClickTicker={(t) => navigate(stockPath(t))}
              />
            </div>
            <div>
              <div className="metric-label mb-2">By sector ({sectorItems.length})</div>
              <HoldingsTreemap
                data={sectorItems}
                displayMode="pct"
                height={300}
                activeName={selectedSector}
                onClickTicker={(sector) =>
                  setPickedSector((cur) => (cur === sector ? null : sector))
                }
              />
            </div>
            <p className="sr-only" role="status">
              {selectedSector
                ? `Showing ${highlightNames?.size ?? 0} stocks in ${selectedSector}`
                : ""}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
