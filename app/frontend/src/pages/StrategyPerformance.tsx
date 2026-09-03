import { useState } from "react";
import { useSearchParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { LineChart as LineChartIcon, Info, Check } from "lucide-react";
import EquityCurveChart from "@/components/EquityCurveChart";
import CompositionPanel from "@/components/CompositionPanel";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { TableFrame } from "@/components/ui/TableFrame";
import { PanelTitle } from "@/components/ui/PanelTitle";
import { usePageMeta, pageTitle } from "@/hooks/usePageMeta";
import { ROUTES } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";
import { seriesColor } from "@/lib/seriesColors";
import { getPerformance, type PerfSeries } from "@/lib/dataService";
import { STRATEGY_BY_ID, perfOrderIndex } from "@/lib/strategies";
import { cn } from "@/lib/utils";

const OUTPERFORM = "hsl(var(--positive))";
const UNDERPERFORM = "hsl(var(--negative))";

const pctFrac = (value: number) => `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
const pp = (value: number) => `${value > 0 ? "+" : ""}${value.toFixed(1)} pp`;

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

/**
 * One legend row per series. The strategy rows are the series toggle
 * (`aria-pressed`); the benchmark row is read-only, it is always on the chart.
 */
function LegendRow({
  series,
  active,
  dimmed,
  onToggle,
}: {
  series: PerfSeries;
  active: boolean;
  dimmed: boolean;
  onToggle?: () => void;
}) {
  const def = STRATEGY_BY_ID[series.id];
  const swatch = (
    <span
      aria-hidden="true"
      className="inline-block h-2.5 w-2.5 shrink-0"
      style={{ backgroundColor: seriesColor(series.id) }}
    />
  );
  const name = (
    <span className="inline-flex items-center gap-2 min-w-0">
      {swatch}
      <span className="truncate">{series.label}</span>
    </span>
  );
  return (
    <tr
      // The whole row is the click target (TradingView-style). The single
      // focusable control stays the button below, so no role/tabIndex here;
      // clicks originating inside it are ignored to avoid toggling twice.
      onClick={
        onToggle
          ? (event) => {
              if ((event.target as HTMLElement).closest("button, a")) return;
              onToggle();
            }
          : undefined
      }
      className={cn(
        "data-table-row",
        dimmed && "opacity-50",
        active && "bg-muted/60",
        onToggle && "cursor-pointer hover:bg-muted/60",
      )}
    >
      <td className="py-1 pl-3 pr-2 text-left">
        {onToggle ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                aria-pressed={active}
                onClick={onToggle}
                className={cn(
                  "inline-flex items-center gap-2 h-8 max-w-full text-left hover:text-foreground",
                  active ? "text-foreground font-medium" : "text-muted-foreground",
                )}
              >
                {name}
                <Check
                  aria-hidden="true"
                  className={cn("h-3.5 w-3.5 shrink-0", !active && "opacity-0")}
                />
              </button>
            </TooltipTrigger>
            {def && (
              <TooltipContent className="max-w-[280px] text-xs font-normal leading-relaxed">
                {def.description}
                {def.note && <span className="mt-1.5 block text-muted-foreground">{def.note}</span>}
              </TooltipContent>
            )}
          </Tooltip>
        ) : (
          <span className="inline-flex items-center h-8 text-muted-foreground">{name}</span>
        )}
      </td>
      <td className={cn("py-1 px-2 text-right", toneClass(series.cumReturn))}>
        {pctFrac(series.cumReturn)}
      </td>
      <td
        className={cn(
          "py-1 px-2 text-right",
          series.excessPp == null ? "text-muted-foreground" : toneClass(series.excessPp),
        )}
      >
        {series.excessPp == null ? "—" : pp(series.excessPp)}
      </td>
      <td className="py-1 px-2 text-right text-muted-foreground hidden sm:table-cell">
        {(series.volatility * 100).toFixed(1)}%
      </td>
      <td className="py-1 pl-2 pr-3 text-right text-muted-foreground hidden sm:table-cell">
        {series.type === "benchmark" ? "—" : `${series.beats}/${series.total}`}
      </td>
    </tr>
  );
}

export default function StrategyPerformance() {
  usePageMeta({
    title: pageTitle("Strategy Performance"),
    description:
      "Backtested returns for every consensus screen, rebalanced each quarter and held to the next, measured against the S&P 500.",
    canonical: canonicalUrl(ROUTES.strategyPerformance),
  });

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

  const startDate = data?.startDate ?? "";
  const windows = data?.quarters?.length ?? 0;

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div>
        <h1 className="page-title">
          <LineChartIcon aria-hidden="true" className="h-5 w-5 text-muted-foreground" />
          Strategy Performance
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">
          How each consensus screen would have performed, rebalanced every quarter and held to the
          next, against the S&amp;P 500.
        </p>
      </div>

      {isLoading ? (
        <LoadingState message="Loading performance…" />
      ) : series.length === 0 ? (
        <EmptyState
          padding="sm"
          title="No consolidated windows yet. A window appears once a quarter has fully elapsed since filing."
        />
      ) : (
        <>
          {/* items-stretch + h-full on both frames: the taller column sets the
              row height, so the two bottom rules land on the same line. */}
          <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] items-stretch">
            <div className="frame flex flex-col h-full overflow-hidden">
              <div className="frame-title frame-title--spaced">
                <PanelTitle>Series</PanelTitle>
              </div>
              <TableFrame label="Strategy legend and series toggle">
                <table className="w-full text-sm" aria-label="Strategy legend and series toggle">
                  <thead>
                    <tr className="text-xs">
                      <th scope="col" className="text-left py-1 pl-3 pr-2">
                        Strategy
                      </th>
                      <th scope="col" className="text-right py-1 px-2">
                        Return
                      </th>
                      <th scope="col" className="text-right py-1 px-2">
                        vs S&amp;P
                      </th>
                      <th scope="col" className="text-right py-1 px-2 hidden sm:table-cell">
                        Vol
                      </th>
                      <th scope="col" className="text-right py-1 pl-2 pr-3 hidden sm:table-cell">
                        Beats
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {strategies.map((s) => (
                      <LegendRow
                        key={s.id}
                        series={s}
                        active={focused === s.id}
                        dimmed={!!focusedSeries && s.id !== focused}
                        onToggle={() => setFocused((prev) => (prev === s.id ? null : s.id))}
                      />
                    ))}
                    {benchmark && (
                      <LegendRow
                        key={benchmark.id}
                        series={benchmark}
                        active={false}
                        dimmed={false}
                      />
                    )}
                  </tbody>
                </table>
              </TableFrame>
              <p className="px-3 pb-3 pt-2 text-xs text-muted-foreground">
                {focusedSeries ? (
                  <>
                    Showing {focusedSeries.label} against the S&amp;P 500.{" "}
                    <button
                      type="button"
                      onClick={() => setFocused(null)}
                      className="inline-flex h-7 items-center rounded-md px-2 text-xs font-medium text-primary-text hover:bg-muted"
                    >
                      Show all
                    </button>
                  </>
                ) : (
                  "Select a strategy to isolate it against the S&P 500 and see its holdings."
                )}
              </p>
            </div>

            <div className="frame flex flex-col h-full overflow-hidden">
              <div className="frame-title frame-title--spaced">
                <PanelTitle>Cumulative return</PanelTitle>
              </div>
              <div className="flex-1 min-h-0 p-3 pt-0">
                <EquityCurveChart
                  series={visible}
                  quarters={data?.quarters ?? []}
                  originLabel={data?.startQuarter}
                  band={band}
                />
              </div>
            </div>
          </div>

          {/* The headline figure, its sample and the disclaimer share one status
              line: the number means nothing without the sample it comes from. */}
          <p className="status-line border-t border-border pt-3 text-muted-foreground">
            {focusedSeries && focusedSeries.excessPp != null ? (
              <>
                <span className="text-foreground">{focusedSeries.label}</span>{" "}
                <span className={toneClass(focusedSeries.excessPp)}>
                  {pp(focusedSeries.excessPp)}
                </span>{" "}
                vs the S&amp;P 500 ({pctFrac(focusedSeries.cumReturn)} against{" "}
                {benchmark ? pctFrac(benchmark.cumReturn) : "—"}), in a descriptive backtest since{" "}
                {startDate} ({longDate(startDate)}), {windows} window
                {windows === 1 ? "" : "s"}, single regime.
              </>
            ) : (
              <>
                Descriptive backtest since {startDate} ({longDate(startDate)}), the earliest 13F in
                the data, {windows} window{windows === 1 ? "" : "s"}, single regime. Benchmark in
                grey.
              </>
            )}{" "}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  aria-label="How this is measured"
                  className="inline-flex items-center justify-center h-6 w-6 align-middle text-muted-foreground hover:text-foreground"
                >
                  <Info className="h-3.5 w-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent className="max-w-[300px] text-xs font-normal leading-relaxed">
                Entered on each quarter's 13F filing date (quarter-end + 45 days, the first day the
                holdings are public; entering earlier would be look-ahead bias), held to the next
                filing, then rebalanced. Conviction-weighted by average portfolio weight, vs the
                S&amp;P 500. Only fully-elapsed quarters are shown, so the sample is small.
              </TooltipContent>
            </Tooltip>{" "}
            <span aria-hidden="true">·</span> Not investment advice
          </p>

          {focusedSeries && <CompositionPanel strategyId={focusedSeries.id} />}
        </>
      )}
    </div>
  );
}
