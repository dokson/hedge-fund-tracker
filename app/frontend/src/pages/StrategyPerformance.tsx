import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2, LineChart as LineChartIcon, Info } from "lucide-react";
import EquityCurveChart from "@/components/EquityCurveChart";
import CompositionPanel from "@/components/CompositionPanel";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { seriesColor } from "@/lib/seriesColors";
import { getPerformance, type PerfSeries } from "@/lib/dataService";
import { STRATEGY_BY_ID, perfOrderIndex } from "@/lib/strategies";
import { cn } from "@/lib/utils";

const OUTPERFORM = "hsl(142, 60%, 45%)";
const UNDERPERFORM = "hsl(0, 68%, 60%)";

const pctFrac = (value: number) => `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;

/** ISO date → "May 15, 2025"; empty string falls through. */
const longDate = (iso: string) =>
  iso
    ? new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : "";

const toneClass = (value: number) =>
  value > 0 ? "delta-positive" : value < 0 ? "delta-negative" : "text-muted-foreground";

function StrategyCard({
  series,
  active,
  onClick,
}: {
  series: PerfSeries;
  active: boolean;
  onClick: () => void;
}) {
  const def = STRATEGY_BY_ID[series.id];
  const Icon = def?.icon;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          aria-pressed={active}
          className={cn(
            "surface p-4 text-left w-full transition-all",
            active ? "ring-2 ring-primary/70" : "hover:border-foreground/40",
          )}
        >
          <div className="flex items-center gap-1.5">
            {Icon ? (
              <Icon className="h-3.5 w-3.5" style={{ color: seriesColor(series.id) }} />
            ) : (
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: seriesColor(series.id) }}
              />
            )}
            <span className="metric-label">{series.label}</span>
          </div>
          <div className={cn("mt-1 text-2xl font-bold font-mono", toneClass(series.cumReturn))}>
            {pctFrac(series.cumReturn)}
          </div>
          <div className="mt-0.5 text-xs font-mono text-muted-foreground">
            Volatility {(series.volatility * 100).toFixed(1)}%
          </div>
        </button>
      </TooltipTrigger>
      {def && (
        <TooltipContent className="max-w-[280px] text-xs font-normal leading-relaxed">
          {def.description}
          {def.note && <span className="mt-1.5 block text-muted-foreground">{def.note}</span>}
        </TooltipContent>
      )}
    </Tooltip>
  );
}

export default function StrategyPerformance() {
  const { data, isLoading } = useQuery({
    queryKey: ["performance"],
    queryFn: getPerformance,
    staleTime: 10 * 60 * 1000,
  });

  // A single focused strategy isolates it against the benchmark; null = show all.
  // Deep-linkable from QuarterlyTrends via ?strategy=<id> (e.g. performanceFor()).
  const [searchParams] = useSearchParams();
  const [focused, setFocused] = useState<string | null>(() => {
    const id = searchParams.get("strategy");
    return id && STRATEGY_BY_ID[id] ? id : null;
  });

  const series = data?.series ?? [];
  const strategies = series
    .filter((s) => s.type === "strategy")
    .sort((a, b) => perfOrderIndex(a.id) - perfOrderIndex(b.id));
  const benchmark = series.find((s) => s.type === "benchmark");
  const focusedSeries = focused ? series.find((s) => s.id === focused) : undefined;
  // Legend order: strategies first, benchmark last.
  const legendSeries = [...strategies, ...(benchmark ? [benchmark] : [])];

  const visible =
    focusedSeries && benchmark
      ? [focusedSeries, benchmark]
      : focusedSeries
        ? [focusedSeries]
        : series;
  const band =
    focusedSeries && benchmark
      ? {
          baseId: benchmark.id,
          topId: focusedSeries.id,
          color: (focusedSeries.excessPp ?? 0) >= 0 ? OUTPERFORM : UNDERPERFORM,
        }
      : undefined;

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div>
        <span className="eyebrow">Backtested track record</span>
        <h1 className="page-title mt-1.5">
          <LineChartIcon className="page-title-icon" /> Strategy Performance
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          How each consensus screen would have performed — rebalanced every quarter and held to the
          next — against the S&amp;P 500.
        </p>
      </div>

      {isLoading ? (
        <div className="surface p-8 flex flex-col items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading performance…</p>
        </div>
      ) : series.length === 0 ? (
        <div className="surface p-8 text-center text-sm text-muted-foreground">
          No consolidated windows yet. A window appears once a quarter has fully elapsed since
          filing.
        </div>
      ) : (
        <>
          {/* Click a card to isolate that strategy vs the S&P 500 on the chart. */}
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
            {strategies.map((s) => (
              <StrategyCard
                key={s.id}
                series={s}
                active={focused === s.id}
                onClick={() => setFocused((prev) => (prev === s.id ? null : s.id))}
              />
            ))}
          </div>

          <div className="surface p-5">
            {/* Legend — pill chips, not interactive (focus is driven by the cards).
                Strategies first, benchmark last; dimmed when not on the chart. */}
            <div className="flex flex-wrap items-center gap-2 mb-4">
              {legendSeries.map((s) => {
                const dimmed = !!focusedSeries && s.type === "strategy" && s.id !== focused;
                const Icon = STRATEGY_BY_ID[s.id]?.icon;
                return (
                  <span
                    key={s.id}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border border-border/60 px-3 py-1 text-xs font-medium text-muted-foreground",
                      dimmed && "opacity-40",
                    )}
                  >
                    {Icon ? (
                      <Icon className="h-3.5 w-3.5" style={{ color: seriesColor(s.id) }} />
                    ) : (
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: seriesColor(s.id) }}
                      />
                    )}
                    {s.label}
                  </span>
                );
              })}
              {focusedSeries ? (
                <button
                  type="button"
                  onClick={() => setFocused(null)}
                  className="text-xs text-primary hover:underline ml-1"
                >
                  Show all
                </button>
              ) : (
                <span className="text-[11px] text-muted-foreground/70 ml-1">
                  Click a strategy card to compare it against the S&amp;P 500 and see its holdings.
                </span>
              )}
            </div>

            <EquityCurveChart
              series={visible}
              quarters={data?.quarters ?? []}
              originLabel={data?.startQuarter}
              band={band}
            />

            <p className="text-xs text-muted-foreground mt-3 inline-flex items-center gap-1.5">
              Cumulative return. The backtest can only begin on {longDate(data?.startDate ?? "")} —
              the earliest 13F filing in the data — so nothing before it is measurable. Benchmark in
              grey.
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    aria-label="How this is measured"
                    className="text-muted-foreground/60 hover:text-foreground"
                  >
                    <Info className="h-3.5 w-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent className="max-w-[300px] text-xs font-normal leading-relaxed">
                  Entered on each quarter's 13F filing date (quarter-end + 45 days — the first day
                  the holdings are public; entering earlier would be look-ahead bias), held to the
                  next filing, then rebalanced. Conviction-weighted by average portfolio weight, vs
                  the S&amp;P 500. Only fully-elapsed quarters are shown, so the sample is small.
                </TooltipContent>
              </Tooltip>
            </p>
          </div>

          {focusedSeries && <CompositionPanel strategyId={focusedSeries.id} />}
        </>
      )}
    </div>
  );
}
