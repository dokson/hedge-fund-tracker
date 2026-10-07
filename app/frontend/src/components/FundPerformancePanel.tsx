import { lazy, Suspense, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { PanelTitle } from "@/components/ui/PanelTitle";
import { useElementSize } from "@/hooks/useElementSize";
import { FUND_SERIES_ID, getFundPerformance, type PerfWindow } from "@/lib/dataService";
import { PLOT_INSET } from "@/lib/equityCurve";
import { pctFrac, pp, toneClass } from "@/lib/performanceFormat";
import { seriesColor } from "@/lib/seriesColors";
import { cn } from "@/lib/utils";

// Lazy so the fund list and the static pages never pull the charting library.
const EquityCurveChart = lazy(() => import("@/components/EquityCurveChart"));

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="bg-card p-3">
      <p className="metric-label">{label}</p>
      <p className={tone ? `text-lg leading-6 ${tone}` : "text-lg leading-6"}>{value}</p>
    </div>
  );
}

const quarterLabel = (quarter: string) => quarter.replace("Q", " Q");

/** Narrowest a quarter column can get before the chart drops axis labels or values touch. */
const MIN_COLUMN_PX = 64;
/** Narrow layout, used where the columns cannot line up with the chart: label and column width. */
const NARROW_LABEL_PX = 72;
const NARROW_COLUMN_PX = 64;

/**
 * One column per quarter, centred under the chart's x-axis point for that quarter (so the
 * chart's own axis names the columns), with the row labels under the origin. When the width
 * cannot keep the columns apart, the quarter names come back as a header and the table scrolls,
 * fading its right edge while there is more to see.
 */
function QuarterTable({
  fundWindows,
  indexWindows,
  lowCoverage,
}: {
  fundWindows: PerfWindow[];
  indexWindows: PerfWindow[];
  lowCoverage: string[];
}) {
  const [containerRef, size] = useElementSize();
  const [moreToTheRight, setMoreToTheRight] = useState(false);
  useEffect(() => {
    const el = containerRef.current;
    if (el) setMoreToTheRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  }, [containerRef, size]);
  const indexBy = new Map(indexWindows.map((w) => [w.quarterOut, w.windowReturn]));
  const flagged = new Set(lowCoverage);
  const count = fundWindows.length;
  if (count === 0) return null;

  const inset = PLOT_INSET.left + PLOT_INSET.right;
  const alignedMinWidth = inset + count * MIN_COLUMN_PX;
  const aligned = size === null || size.width >= alignedMinWidth;
  const step = `(100% - ${inset}px) / ${count}`;
  const gridStyle = aligned
    ? {
        gridTemplateColumns: [
          `calc(${PLOT_INSET.left}px + ${step} / 2)`,
          ...Array.from({ length: count - 1 }, () => `calc(${step})`),
          `calc(${step} / 2 + ${PLOT_INSET.right}px)`,
        ].join(" "),
      }
    : {
        gridTemplateColumns: `${NARROW_LABEL_PX}px repeat(${count}, minmax(${NARROW_COLUMN_PX}px, 1fr))`,
      };
  const minWidth = aligned ? alignedMinWidth : NARROW_LABEL_PX + count * NARROW_COLUMN_PX;
  const cellAlign = (i: number) => (aligned && i === count - 1 ? "text-right" : "text-center");
  const cell = "py-1.5 tabular-nums";
  const rowLabel = "sticky left-0 bg-card py-1.5 text-left text-muted-foreground";

  return (
    <div className="border-t border-border px-3">
      <div
        ref={containerRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          setMoreToTheRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
        }}
        className={cn(
          "overflow-x-auto",
          moreToTheRight &&
            "[mask-image:linear-gradient(to_right,black_calc(100%-28px),transparent)]",
        )}
      >
        <div
          role="table"
          aria-label="Quarter by quarter"
          className="whitespace-nowrap text-xs"
          style={{ minWidth }}
        >
          <div
            role="row"
            className={cn("grid text-muted-foreground", aligned && "sr-only")}
            style={gridStyle}
          >
            <div role="columnheader" />
            {fundWindows.map((w, i) => (
              <div key={w.quarterOut} role="columnheader" className={cn(cell, cellAlign(i))}>
                {quarterLabel(w.quarterOut)}
                {flagged.has(w.quarterOut) && <span className="text-warning"> *</span>}
              </div>
            ))}
          </div>
          <div role="row" className="grid" style={gridStyle}>
            <div role="rowheader" className={rowLabel}>
              Fund
            </div>
            {fundWindows.map((w, i) => (
              <div
                key={w.quarterOut}
                role="cell"
                className={cn(cell, cellAlign(i), toneClass(w.windowReturn))}
              >
                <span className="relative">
                  {pctFrac(w.windowReturn)}
                  {flagged.has(w.quarterOut) && (
                    <span aria-hidden="true" className="absolute right-full mr-0.5 text-warning">
                      *
                    </span>
                  )}
                </span>
              </div>
            ))}
          </div>
          <div role="row" className="grid" style={gridStyle}>
            <div role="rowheader" className={rowLabel}>
              S&amp;P 500
            </div>
            {fundWindows.map((w, i) => {
              const value = indexBy.get(w.quarterOut);
              return (
                <div key={w.quarterOut} role="cell" className={cn(cell, cellAlign(i))}>
                  {value === undefined ? "—" : pctFrac(value)}
                </div>
              );
            })}
          </div>
          <div role="row" className="grid border-t border-border font-medium" style={gridStyle}>
            <div role="rowheader" className={cn(rowLabel, "font-normal")}>
              Difference
            </div>
            {fundWindows.map((w, i) => {
              const gap = w.excessReturn === null ? null : w.excessReturn * 100;
              return (
                <div
                  key={w.quarterOut}
                  role="cell"
                  className={cn(cell, cellAlign(i), gap !== null && toneClass(gap))}
                  aria-label={
                    gap === null
                      ? undefined
                      : `${quarterLabel(w.quarterOut)}: ${gap >= 0 ? "beat" : "trailed"} the S&P 500 by ${Math.abs(gap).toFixed(1)} pp`
                  }
                >
                  {gap === null ? "—" : pp(gap)}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * The fund's quarter-by-quarter track record against the S&P 500. It describes
 * the whole history, so it stays the same whichever quarter the page shows;
 * nothing renders for a fund without a measured quarter.
 */
export default function FundPerformancePanel({ fund }: { fund: string }) {
  const { data } = useQuery({
    queryKey: ["fundPerformance", fund],
    queryFn: () => getFundPerformance(fund),
  });
  if (!data) return null;

  const fundSeries = data.series.find((s) => s.id === FUND_SERIES_ID);
  const index = data.series.find((s) => s.type === "benchmark");
  if (!fundSeries) return null;
  const firstQuarter = data.quarters[0] ?? "";

  return (
    <section className="frame overflow-hidden" aria-labelledby="fund-track-record">
      <div className="frame-title">
        <PanelTitle id="fund-track-record">Estimated return</PanelTitle>
      </div>
      <p className="px-3 pb-3 text-xs leading-5 text-muted-foreground">
        Price-only return of the fund&apos;s top 100 US longs at each quarter start, since{" "}
        {firstQuarter.replace("Q", " Q")}, vs the S&amp;P 500. Not its actual return (no trades,
        fees, shorts, derivatives, cash). Not investment advice.
      </p>
      <div className="grid grid-cols-2 gap-px border-y border-border bg-border sm:grid-cols-4">
        <Stat
          label="Fund"
          value={pctFrac(fundSeries.cumReturn)}
          tone={toneClass(fundSeries.cumReturn)}
        />
        <Stat label="S&P 500" value={index && index.total > 0 ? pctFrac(index.cumReturn) : "—"} />
        <Stat
          label="Excess"
          value={fundSeries.excessPp === null ? "—" : pp(fundSeries.excessPp)}
          tone={fundSeries.excessPp === null ? undefined : toneClass(fundSeries.excessPp)}
        />
        <Stat label="Quarters beating" value={`${fundSeries.beats} of ${fundSeries.total}`} />
      </div>
      {/* EquityCurveChart sets its own 340px floor; a fixed box shorter than that overflows. */}
      <div className="px-3 pt-3">
        <Suspense fallback={null}>
          <EquityCurveChart
            series={data.series}
            quarters={data.quarters}
            originLabel={data.startQuarter}
            band={
              index
                ? { baseId: index.id, topId: fundSeries.id, color: seriesColor(fundSeries.id) }
                : undefined
            }
          />
        </Suspense>
      </div>
      <QuarterTable
        fundWindows={fundSeries.windows}
        indexWindows={index?.windows ?? []}
        lowCoverage={data.lowCoverage}
      />
      {data.lowCoverage.length > 0 && (
        <p className="border-t border-border px-3 py-2 text-xs text-warning">
          * {data.lowCoverage.map((q) => q.replace("Q", " Q")).join(", ")}: over 5% of the book
          could not be priced, so those quarters are less reliable.
        </p>
      )}
    </section>
  );
}
