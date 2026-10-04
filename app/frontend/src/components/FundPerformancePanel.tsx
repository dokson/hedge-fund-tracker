import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";

import { PanelTitle } from "@/components/ui/PanelTitle";
import { FUND_SERIES_ID, getFundPerformance, type PerfWindow } from "@/lib/dataService";
import { pctFrac, pp, toneClass } from "@/lib/performanceFormat";
import { seriesColor } from "@/lib/seriesColors";

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

/**
 * One column per quarter: the fund, the index and the gap between them, so the
 * quarters the fund trailed stand out by sign and colour, not only in the count.
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
  const indexBy = new Map(indexWindows.map((w) => [w.quarterOut, w.windowReturn]));
  const flagged = new Set(lowCoverage);
  const cell = "px-3 py-1.5 text-right tabular-nums";
  return (
    <div className="overflow-x-auto border-t border-border">
      <table className="w-full whitespace-nowrap text-xs" aria-label="Quarter by quarter">
        <thead>
          <tr className="text-muted-foreground">
            <th scope="col" className="px-3 py-1.5 text-left font-normal" />
            {fundWindows.map((w) => (
              <th key={w.quarterOut} scope="col" className={`${cell} font-normal`}>
                {quarterLabel(w.quarterOut)}
                {flagged.has(w.quarterOut) && <span className="text-warning"> *</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row" className="px-3 py-1.5 text-left font-normal text-muted-foreground">
              Fund
            </th>
            {fundWindows.map((w) => (
              <td key={w.quarterOut} className={`${cell} ${toneClass(w.windowReturn)}`}>
                {pctFrac(w.windowReturn)}
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row" className="px-3 py-1.5 text-left font-normal text-muted-foreground">
              S&amp;P 500
            </th>
            {fundWindows.map((w) => {
              const value = indexBy.get(w.quarterOut);
              return (
                <td key={w.quarterOut} className={cell}>
                  {value === undefined ? "—" : pctFrac(value)}
                </td>
              );
            })}
          </tr>
          <tr className="border-t border-border font-medium">
            <th scope="row" className="px-3 py-1.5 text-left font-normal text-muted-foreground">
              Difference
            </th>
            {fundWindows.map((w) => {
              const gap = w.excessReturn === null ? null : w.excessReturn * 100;
              return (
                <td
                  key={w.quarterOut}
                  className={`${cell} ${gap === null ? "" : toneClass(gap)}`}
                  aria-label={
                    gap === null
                      ? undefined
                      : `${quarterLabel(w.quarterOut)}: ${gap >= 0 ? "beat" : "trailed"} the S&P 500 by ${Math.abs(gap).toFixed(1)} pp`
                  }
                >
                  {gap === null ? "—" : pp(gap)}
                </td>
              );
            })}
          </tr>
        </tbody>
      </table>
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
      <p className="max-w-[95ch] px-3 pb-3 text-xs leading-5 text-muted-foreground">
        Estimated return of the fund&apos;s disclosed US long positions at the start of each quarter
        (top 100 by value), price-only, since {firstQuarter.replace("Q", " Q")}. Not the fund&apos;s
        actual return: excludes trading within the quarter, fees, shorts, derivatives and cash.
        Benchmark: S&amp;P 500 price return over the same quarter-end windows. Not investment
        advice.
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
