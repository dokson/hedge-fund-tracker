import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { LineChart as LineChartIcon, Check } from "lucide-react";
import EquityCurveChart from "@/components/EquityCurveChart";
import CompositionPanel from "@/components/CompositionPanel";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { QueryState } from "@/components/ui/QueryState";
import { TableFrame } from "@/components/ui/TableFrame";
import { PanelTitle } from "@/components/ui/PanelTitle";
import { usePageMeta } from "@/hooks/usePageMeta";
import { PERFORMANCE_PAGE } from "@/lib/pageMeta";
import { canonicalUrl } from "@/lib/seo";
import { learnItem } from "@/lib/routes";
import { seriesColor } from "@/lib/seriesColors";
import { getPerformance, type PerfSeries } from "@/lib/dataService";
import { STRATEGY_BY_ID, perfOrderIndex } from "@/lib/strategies";
import { pctFrac, pp, toneClass } from "@/lib/performanceFormat";
import { cn } from "@/lib/utils";

const OUTPERFORM = "hsl(var(--positive))";
const UNDERPERFORM = "hsl(var(--negative))";

/** ISO date → "May 15, 2025"; empty string falls through. */
const longDate = (iso: string) =>
  iso
    ? new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : "";

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
      // The whole row is the click target. The single focusable control stays
      // the button below; ignore its click here to avoid toggling twice.
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
      <td className={cn("py-1 px-2 text-right whitespace-nowrap", toneClass(series.cumReturn))}>
        {pctFrac(series.cumReturn)}
      </td>
      <td
        className={cn(
          "py-1 px-2 text-right whitespace-nowrap",
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
    title: PERFORMANCE_PAGE.title,
    description: PERFORMANCE_PAGE.description,
    canonical: canonicalUrl(PERFORMANCE_PAGE.path),
  });

  const { data, isLoading, isError, error } = useQuery({
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
  const lastQuarter = data?.quarters.at(-1) ?? "";

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div>
        <h1 className="page-title">
          <LineChartIcon aria-hidden="true" className="h-5 w-5 text-muted-foreground" />
          Strategy Performance
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">
          A descriptive backtest of each consensus screen, rebalanced quarterly and held to the next
          window, against the S&amp;P 500.
        </p>
      </div>

      {isError ? (
        <QueryState isError error={error} title="Could not load performance data" />
      ) : isLoading ? (
        <LoadingState message="Loading performance…" />
      ) : series.length === 0 ? (
        <EmptyState
          padding="sm"
          title="No consolidated windows yet. A window appears once a quarter has fully elapsed since filing."
        />
      ) : (
        <>
          <div className="space-y-2 border-y border-border py-3 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">
              {longDate(startDate)} → {lastQuarter} exit · {windows} completed window
              {windows === 1 ? "" : "s"}
            </p>
            <p className="max-w-3xl">
              A tiny, single-regime sample, using a fund roster preselected on past performance.
              These results describe this window; they do not establish an investing edge.{" "}
              <Link
                to={learnItem("how-strategy-performance-is-backtested")}
                className="text-primary-text hover:underline underline-offset-4"
              >
                Backtest method &amp; limits
              </Link>
            </p>
          </div>
          {/* Mobile keeps the plot and its compact controls together, before the detail table. */}
          <div className="grid items-stretch gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            <div className="frame order-2 flex h-full flex-col overflow-hidden md:order-1">
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
                        vs S&amp;P (pp)
                      </th>
                      <th scope="col" className="text-right py-1 px-2 hidden sm:table-cell">
                        Vol (qtr)
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
              <p className="px-3 pt-2 text-xs text-muted-foreground">
                Excess is in percentage points (pp). Volatility is the variation in quarterly
                returns, not annualized. Beats counts windows ahead of the S&amp;P 500.
              </p>
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

            <div className="frame order-1 flex h-full flex-col overflow-hidden md:order-2">
              <div className="frame-title frame-title--spaced">
                <PanelTitle>Cumulative return</PanelTitle>
                <span className="hidden text-xs font-normal text-muted-foreground md:block">
                  Hover to compare
                </span>
              </div>
              <div className="flex-1 min-h-0 p-3 pt-0">
                <EquityCurveChart
                  series={visible}
                  quarters={data?.quarters ?? []}
                  originLabel={data?.startQuarter}
                  band={band}
                  className="h-[260px] min-h-[260px] md:h-full md:min-h-[340px]"
                />
              </div>
              <div
                role="group"
                aria-label="Chart series"
                className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 pb-3 md:hidden"
              >
                {strategies.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    aria-pressed={focused === s.id}
                    onClick={() => setFocused((prev) => (prev === s.id ? null : s.id))}
                    className={cn(
                      "inline-flex min-h-8 items-center gap-1.5 rounded-sm text-xs hover:text-foreground",
                      focused === s.id ? "font-semibold text-foreground" : "text-muted-foreground",
                      focusedSeries && focused !== s.id && "opacity-50",
                    )}
                  >
                    <span
                      aria-hidden="true"
                      className="h-2 w-2 shrink-0"
                      style={{ backgroundColor: seriesColor(s.id) }}
                    />
                    {s.label}
                  </button>
                ))}
                {benchmark && (
                  <span className="inline-flex min-h-8 items-center gap-1.5 text-xs text-muted-foreground">
                    <span
                      aria-hidden="true"
                      className="h-2 w-2 shrink-0"
                      style={{ backgroundColor: seriesColor(benchmark.id) }}
                    />
                    {benchmark.label}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* The isolated strategy's comparison follows the chart; sample limits stay above it. */}
          <p className="status-line border-t border-border pt-3 text-muted-foreground">
            {focusedSeries && focusedSeries.excessPp != null ? (
              <>
                <span className="text-foreground">{focusedSeries.label}</span>{" "}
                <span className={toneClass(focusedSeries.excessPp)}>
                  {pp(focusedSeries.excessPp)}
                </span>{" "}
                vs the S&amp;P 500 ({pctFrac(focusedSeries.cumReturn)} against{" "}
                {benchmark ? pctFrac(benchmark.cumReturn) : "—"}).
              </>
            ) : (
              <>All strategies shown against the S&amp;P 500 benchmark in grey.</>
            )}
          </p>

          {focusedSeries && <CompositionPanel strategyId={focusedSeries.id} />}
        </>
      )}
    </div>
  );
}
