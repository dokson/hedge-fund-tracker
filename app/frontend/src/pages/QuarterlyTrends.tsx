import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  runQuarterAnalysis,
  getQuarterFundList,
  formatValue,
  formatPct,
  type StockQuarterAnalysis,
} from "@/lib/dataService";
import type { Quarter } from "@/lib/quarters";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { TickerLink } from "@/components/EntityLinks";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Loader2, TrendingUp, TrendingDown, Handshake, Sparkles, Banknote, PieChart, BarChart3, Info, Star, Filter, Users, Building2 } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useStarred } from "@/hooks/useStarred";
import { Badge } from "@/components/ui/badge";

type SortKey = keyof StockQuarterAnalysis;

function SortableHeader({
  label, sortKey, currentKey, currentDir, onSort, align = "right", tooltip,
}: {
  label: string; sortKey: SortKey; currentKey: SortKey; currentDir: "asc" | "desc";
  onSort: (k: SortKey) => void; align?: "left" | "right"; tooltip?: string;
}) {
  const indicator = currentKey === sortKey ? (currentDir === "desc" ? " ↓" : " ↑") : "";
  return (
    <th
      className={`text-${align} p-3 font-medium cursor-pointer hover:text-foreground`}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-1">
        {label}{indicator}
        {tooltip && (
          <Tooltip>
            <TooltipTrigger asChild><Info className="h-3 w-3 text-muted-foreground/60 cursor-help" /></TooltipTrigger>
            <TooltipContent side="top" className="max-w-[280px] text-xs font-normal normal-case tracking-normal"><p>{tooltip}</p></TooltipContent>
          </Tooltip>
        )}
      </span>
    </th>
  );
}

function AnalysisTable({
  data,
  defaultSort,
  defaultDir = "desc",
  columns,
  defaultMinHolders = 0,
  defaultFilterInfinite = false,
  defaultLimit = 30,
  disableFilters = false,
}: {
  data: StockQuarterAnalysis[];
  defaultSort: SortKey;
  defaultDir?: "asc" | "desc";
  columns: { key: SortKey; label: string; align?: "left" | "right"; format?: (v: any, row: StockQuarterAnalysis) => string; colorFn?: (v: any) => string; tooltip?: string }[];
  defaultMinHolders?: number;
  defaultFilterInfinite?: boolean;
  defaultLimit?: number;
  disableFilters?: boolean;
}) {
  const navigate = useNavigate();
  const [sortKey, setSortKey] = useState<SortKey>(defaultSort);
  const [sortDir, setSortDir] = useState<"asc" | "desc">(defaultDir);
  const [minHolders, setMinHolders] = useState(defaultMinHolders);
  const [filterInfinite, setFilterInfinite] = useState(defaultFilterInfinite);
  const [limit, setLimit] = useState(defaultLimit);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortKey(key); setSortDir("desc"); }
  }

  const filtered = useMemo(() => {
    if (disableFilters) return data;
    let arr = data.filter((s) => s.holderCount >= minHolders);
    if (filterInfinite) arr = arr.filter((s) => isFinite(s.delta));
    return arr;
  }, [data, minHolders, filterInfinite, disableFilters]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      const va = a[sortKey] as number;
      const vb = b[sortKey] as number;
      if (!isFinite(va) && !isFinite(vb)) return 0;
      if (!isFinite(va)) return sortDir === "desc" ? -1 : 1;
      if (!isFinite(vb)) return sortDir === "desc" ? 1 : -1;
      return sortDir === "desc" ? vb - va : va - vb;
    });
    return disableFilters ? arr : arr.slice(0, limit);
  }, [filtered, sortKey, sortDir, limit, disableFilters]);

  return (
    <div className="space-y-3">
      {/* Filter controls */}
      <div className={`flex flex-wrap items-center gap-4 text-sm ${disableFilters ? "opacity-40 pointer-events-none" : ""}`}>
        <span className="text-xs text-muted-foreground flex items-center gap-1"><Filter className="h-3 w-3" /> Filters:</span>
        <div className="flex items-center gap-2">
          <Label htmlFor="minHolders" className="text-xs text-muted-foreground whitespace-nowrap">Min Holders</Label>
          <div className="flex items-center h-8 rounded-md border border-border bg-card overflow-hidden">
            <button
              type="button"
              onClick={() => setMinHolders(Math.max(0, minHolders - 1))}
              className="px-2 h-full text-muted-foreground hover:text-foreground hover:bg-muted transition-colors text-sm"
            >−</button>
            <Input
              id="minHolders"
              type="number"
              min={0}
              value={minHolders}
              onChange={(e) => setMinHolders(parseInt(e.target.value) || 0)}
              className="w-10 h-full border-0 bg-transparent text-xs text-center p-0 rounded-none focus-visible:ring-0"
            />
            <button
              type="button"
              onClick={() => setMinHolders(minHolders + 1)}
              className="px-2 h-full text-muted-foreground hover:text-foreground hover:bg-muted transition-colors text-sm"
            >+</button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Label htmlFor="excludeInf" className="text-xs text-muted-foreground whitespace-nowrap">Exclude NEW</Label>
          <Switch
            id="excludeInf"
            checked={filterInfinite}
            onCheckedChange={setFilterInfinite}
          />
        </div>
        <div className="flex items-center gap-2">
          <Label htmlFor="limit" className="text-xs text-muted-foreground whitespace-nowrap">Show top</Label>
          <Select value={String(limit)} onValueChange={(v) => setLimit(parseInt(v))}>
            <SelectTrigger className="w-20 h-8 bg-card border-border text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="15">15</SelectItem>
              <SelectItem value="30">30</SelectItem>
              <SelectItem value="50">50</SelectItem>
              <SelectItem value="100">100</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <span className="text-xs text-muted-foreground ml-auto">{filtered.length} stocks matching</span>
      </div>

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-muted-foreground uppercase tracking-wider">
                <th className="text-right p-3 font-medium w-12">#</th>
                <th className="text-left p-3 font-medium">Ticker</th>
                <th className="text-left p-3 font-medium">Company</th>
                {columns.map((col) => (
                  <SortableHeader
                    key={col.key}
                    label={col.label}
                    sortKey={col.key}
                    currentKey={sortKey}
                    currentDir={sortDir}
                    onSort={toggleSort}
                    align={col.align || "right"}
                    tooltip={col.tooltip}
                  />
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.length === 0 ? (
                <tr>
                  <td colSpan={3 + columns.length} className="p-8 text-center text-muted-foreground">
                    No data available.
                  </td>
                </tr>
              ) : (
                sorted.map((s, index) => (
                  <tr key={s.ticker} className="data-table-row">
                    <td className="p-3 text-right text-muted-foreground font-mono text-xs">{index + 1}</td>
                    <td className="p-3"><TickerLink ticker={s.ticker} /></td>
                    <td className="p-3 text-muted-foreground max-w-[200px] truncate cursor-pointer hover:text-foreground transition-colors" onClick={() => navigate(`/stock/${s.ticker}`)}>{s.company}</td>
                    {columns.map((col) => {
                      const rawVal = s[col.key];
                      const display = col.format ? col.format(rawVal, s) : String(rawVal);
                      const colorClass = col.colorFn ? col.colorFn(rawVal) : "";
                      return (
                        <td key={col.key} className={`p-3 text-${col.align || "right"} font-mono ${colorClass}`}>
                          {display}
                        </td>
                      );
                    })}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const deltaColor = (v: number) => !isFinite(v) ? "delta-positive" : v > 0 ? "delta-positive" : v < 0 ? "delta-negative" : "";
const netColor = (v: number) => v > 0 ? "delta-positive" : v < 0 ? "delta-negative" : "";

export default function QuarterlyTrends() {
  const navigate = useNavigate();
  const { quarters, latestQuarter } = useAvailableQuarters();
  const [selectedQuarter, setSelectedQuarter] = useState<Quarter | undefined>();
  const quarter = selectedQuarter ?? latestQuarter;
  const [progress, setProgress] = useState({ msg: "", pct: 0 });
  const { starred: starredStocks } = useStarred("stock");
  const { starred: starredFunds } = useStarred("fund");
  const [filterStarredStocks, setFilterStarredStocks] = useState(false);
  const [filterStarredFunds, setFilterStarredFunds] = useState(false);
  const anyStarredFilter = filterStarredStocks || filterStarredFunds;
  const hasAnyStarred = starredStocks.size > 0 || starredFunds.size > 0;

  const activeFundFilter = filterStarredFunds && starredFunds.size > 0 ? starredFunds : undefined;

  const { data: rawData = [], isLoading } = useQuery({
    queryKey: ["quarterAnalysis", quarter, activeFundFilter ? [...activeFundFilter].sort().join(",") : "all"],
    queryFn: () => runQuarterAnalysis(quarter!, (msg, pct) => setProgress({ msg, pct }), activeFundFilter),
    enabled: !!quarter,
    staleTime: 10 * 60 * 1000,
  });

  const { data: quarterFundList = [] } = useQuery({
    queryKey: ["quarterFundList", quarter],
    queryFn: () => getQuarterFundList(quarter!),
    enabled: !!quarter,
    staleTime: Infinity,
  });
  const defaultMinHolders = Math.max(1, Math.ceil(quarterFundList.length * 0.1));

  const data = useMemo(() => {
    if (filterStarredStocks && starredStocks.size > 0) {
      return rawData.filter((s) => starredStocks.has(s.ticker));
    }
    return rawData;
  }, [rawData, filterStarredStocks, starredStocks]);



  return (
    <div className="space-y-5 max-w-7xl">
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2"><BarChart3 className="h-6 w-6" /> Quarterly Trends</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Cross-fund consensus signals — {data.length} stocks analyzed
              {(filterStarredStocks || filterStarredFunds) && (
                <span className="ml-1 text-primary">(filtered)</span>
              )}
            </p>
          </div>
          <Select value={quarter ?? ""} onValueChange={(v) => setSelectedQuarter(v as Quarter)}>
            <SelectTrigger className="w-36 bg-card border-border">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[...quarters].reverse().map((q) => (
                <SelectItem key={q} value={q}>{q.replace("Q", " Q")}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

      </div>

      {isLoading ? (
        <div className="rounded-lg border border-border bg-card p-8">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">{progress.msg}</p>
            <Progress value={progress.pct} className="w-64" />
          </div>
        </div>
      ) : (
        <Tabs defaultValue="avgportfolio" className="w-full">
          <TabsList className="bg-secondary border border-border h-auto flex-wrap">
            <Tooltip><TooltipTrigger asChild><span><TabsTrigger value="avgportfolio" className="gap-1.5"><PieChart className="h-3.5 w-3.5" /> Avg Portfolio</TabsTrigger></span></TooltipTrigger><TooltipContent className="max-w-[280px] text-xs font-normal">Stocks ranked by average portfolio weight across all tracked funds.</TooltipContent></Tooltip>
            <Tooltip><TooltipTrigger asChild><span><TabsTrigger value="consensus" className="gap-1.5"><Handshake className="h-3.5 w-3.5" /> Consensus Buys</TabsTrigger></span></TooltipTrigger><TooltipContent className="max-w-[280px] text-xs font-normal">Stocks with the most net buyers (buyers minus sellers) this quarter.</TooltipContent></Tooltip>
            <Tooltip><TooltipTrigger asChild><span><TabsTrigger value="new" className="gap-1.5"><Sparkles className="h-3.5 w-3.5" /> New Consensus</TabsTrigger></span></TooltipTrigger><TooltipContent className="max-w-[280px] text-xs font-normal">Stocks attracting the most brand-new holders this quarter.</TooltipContent></Tooltip>
            <Tooltip><TooltipTrigger asChild><span><TabsTrigger value="bigbets" className="gap-1.5"><Banknote className="h-3.5 w-3.5" /> Big Bets</TabsTrigger></span></TooltipTrigger><TooltipContent className="max-w-[280px] text-xs font-normal">Stocks with the highest portfolio concentration in a single fund.</TooltipContent></Tooltip>
            <Tooltip><TooltipTrigger asChild><span><TabsTrigger value="increasing" className="gap-1.5"><TrendingUp className="h-3.5 w-3.5" /> Increasing Positions</TabsTrigger></span></TooltipTrigger><TooltipContent className="max-w-[280px] text-xs font-normal">Stocks with the largest percentage increase in aggregate shares held.</TooltipContent></Tooltip>
            <Tooltip><TooltipTrigger asChild><span><TabsTrigger value="decreasing" className="gap-1.5"><TrendingDown className="h-3.5 w-3.5" /> Decreasing Positions</TabsTrigger></span></TooltipTrigger><TooltipContent className="max-w-[280px] text-xs font-normal">Stocks with the largest percentage decrease in aggregate shares held.</TooltipContent></Tooltip>
          </TabsList>

          {/* Starred filters */}
          {hasAnyStarred && (
            <div className="flex flex-wrap items-center gap-3 mt-4">
              <span className="text-xs text-muted-foreground flex items-center gap-1"><Star className="h-3 w-3" fill="currentColor" /> Consider Starred only:</span>
              <button
                onClick={() => starredFunds.size > 0 && setFilterStarredFunds((v) => !v)}
                disabled={starredFunds.size === 0}
                className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md border transition-colors ${
                  filterStarredFunds
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-card border-border text-muted-foreground hover:text-foreground hover:border-foreground/30"
                } disabled:opacity-40 disabled:cursor-not-allowed`}
              >
                <Users className="h-3 w-3" /> Funds
                <Badge variant="secondary" className="text-[9px] px-1.5 py-0 h-4 leading-none">{starredFunds.size}</Badge>
              </button>
              <button
                onClick={() => starredStocks.size > 0 && setFilterStarredStocks((v) => !v)}
                disabled={starredStocks.size === 0}
                className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md border transition-colors ${
                  filterStarredStocks
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-card border-border text-muted-foreground hover:text-foreground hover:border-foreground/30"
                } disabled:opacity-40 disabled:cursor-not-allowed`}
              >
                <Building2 className="h-3 w-3" /> Stocks
                <Badge variant="secondary" className="text-[9px] px-1.5 py-0 h-4 leading-none">{starredStocks.size}</Badge>
              </button>
            </div>
          )}

          <TabsContent value="consensus" className="mt-4">
             <AnalysisTable
              data={data}
              defaultSort="netBuyers"
              disableFilters={anyStarredFilter}
              columns={[
                { key: "delta", label: "Δ%", format: (v) => formatPct(v, true), colorFn: deltaColor, tooltip: "Percentage change in aggregate shares held vs previous quarter." },
                { key: "netBuyers", label: "Net Buyers", colorFn: netColor, tooltip: "Buyers minus sellers this quarter." },
                { key: "buyerCount", label: "Buyers", tooltip: "Number of funds that increased their position." },
                { key: "sellerCount", label: "Sellers", tooltip: "Number of funds that decreased their position." },
                { key: "holderCount", label: "Holders", tooltip: "Total number of tracked funds holding this stock." },
                { key: "totalDeltaValue", label: "Δ Value", format: (v) => formatValue(v), colorFn: netColor, tooltip: "Net change in dollar value across all holders." },
              ]}
            />
          </TabsContent>

          <TabsContent value="new" className="mt-4">
             <AnalysisTable
              data={data}
              defaultSort="newHolderCount"
              disableFilters={anyStarredFilter}
              columns={[
                { key: "newHolderCount", label: "New Holders", tooltip: "Funds that opened a brand-new position this quarter." },
                { key: "netBuyers", label: "Net Buyers", colorFn: netColor, tooltip: "Buyers minus sellers this quarter." },
                { key: "holderCount", label: "Holders", tooltip: "Total number of tracked funds holding this stock." },
                { key: "delta", label: "Δ%", format: (v) => formatPct(v, true), colorFn: deltaColor, tooltip: "Percentage change in aggregate shares held." },
                { key: "totalDeltaValue", label: "Δ Value", format: (v) => formatValue(v), colorFn: netColor, tooltip: "Net change in dollar value across all holders." },
                { key: "totalValue", label: "Total Value", format: (v) => formatValue(v), tooltip: "Total institutional value across all tracked holders." },
              ]}
            />
          </TabsContent>

          <TabsContent value="increasing" className="mt-4">
             <AnalysisTable
              data={data}
              defaultSort="delta"
              defaultFilterInfinite
              defaultMinHolders={defaultMinHolders}
              disableFilters={anyStarredFilter}
              columns={[
                { key: "newHolderCount", label: "New Holders", tooltip: "Funds that opened a brand-new position this quarter." },
                { key: "netBuyers", label: "Net Buyers", colorFn: netColor, tooltip: "Buyers minus sellers this quarter." },
                { key: "holderCount", label: "Holders", tooltip: "Total number of tracked funds holding this stock." },
                { key: "delta", label: "Δ%", format: (v) => formatPct(v, true), colorFn: deltaColor, tooltip: "Percentage change in aggregate shares held." },
                { key: "totalDeltaValue", label: "Δ Value", format: (v) => formatValue(v), colorFn: netColor, tooltip: "Net change in dollar value across all holders." },
                { key: "totalValue", label: "Total Value", format: (v) => formatValue(v), tooltip: "Total institutional value across all tracked holders." },
              ]}
            />
          </TabsContent>

          <TabsContent value="decreasing" className="mt-4">
             <AnalysisTable
              data={data}
              defaultSort="delta"
              defaultDir="asc"
              defaultMinHolders={defaultMinHolders}
              disableFilters={anyStarredFilter}
              columns={[
                { key: "closeCount", label: "Closers", tooltip: "Funds that completely exited their position this quarter." },
                { key: "netBuyers", label: "Net Buyers", colorFn: netColor, tooltip: "Buyers minus sellers this quarter." },
                { key: "holderCount", label: "Holders", tooltip: "Total number of tracked funds holding this stock." },
                { key: "delta", label: "Δ%", format: (v) => formatPct(v, true), colorFn: deltaColor, tooltip: "Percentage change in aggregate shares held." },
                { key: "totalDeltaValue", label: "Δ Value", format: (v) => formatValue(v), colorFn: netColor, tooltip: "Net change in dollar value across all holders." },
                { key: "totalValue", label: "Total Value", format: (v) => formatValue(v), tooltip: "Total institutional value across all tracked holders." },
              ]}
            />
          </TabsContent>

          <TabsContent value="bigbets" className="mt-4">
             <AnalysisTable
              data={data}
              defaultSort="maxPortfolioPct"
              disableFilters={anyStarredFilter}
              columns={[
                { key: "maxPortfolioPct", label: "Max Ptf %", format: (v) => `${v.toFixed(1)}%`, tooltip: "Highest portfolio weight allocated by any single fund." },
                { key: "avgPortfolioPct", label: "Avg Ptf %", format: (v) => `${v.toFixed(2)}%`, tooltip: "Average portfolio weight across all holding funds." },
                { key: "delta", label: "Δ%", format: (v) => formatPct(v, true), colorFn: deltaColor, tooltip: "Percentage change in aggregate shares held." },
                { key: "totalDeltaValue", label: "Δ Value", format: (v) => formatValue(v), colorFn: netColor, tooltip: "Net change in dollar value across all holders." },
                { key: "totalValue", label: "Total Value", format: (v) => formatValue(v), tooltip: "Total institutional value across all tracked holders." },
              ]}
            />
          </TabsContent>

          <TabsContent value="avgportfolio" className="mt-4">
             <AnalysisTable
              data={data}
              defaultSort="avgPortfolioPct"
              defaultMinHolders={defaultMinHolders}
              disableFilters={anyStarredFilter}
              columns={[
                { key: "avgPortfolioPct", label: "Avg Ptf %", format: (v) => `${v.toFixed(2)}%`, tooltip: "Average portfolio weight across all holding funds." },
                { key: "maxPortfolioPct", label: "Max Ptf %", format: (v) => `${v.toFixed(1)}%`, tooltip: "Highest portfolio weight allocated by any single fund." },
                { key: "holderCount", label: "Holders", tooltip: "Total number of tracked funds holding this stock." },
                { key: "delta", label: "Δ%", format: (v) => formatPct(v, true), colorFn: deltaColor, tooltip: "Percentage change in aggregate shares held." },
              ]}
            />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
