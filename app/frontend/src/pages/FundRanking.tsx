import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Info, Trophy } from "lucide-react";

import { FundCell } from "@/components/EntityLinks";
import { ColumnHeader } from "@/components/ui/ColumnHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { PanelTitle } from "@/components/ui/PanelTitle";
import { QueryState } from "@/components/ui/QueryState";
import { TableFrame } from "@/components/ui/TableFrame";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useSortState } from "@/hooks/useSortState";
import { getFundPerformanceRows } from "@/lib/dataService";
import { rankFunds, sortRanking, type RankedFund, type RankingKey } from "@/lib/fundRanking";
import { RANKING_PAGE } from "@/lib/pageMeta";
import { pctFrac, toneClass } from "@/lib/performanceFormat";
import { canonicalUrl } from "@/lib/seo";
import { cn } from "@/lib/utils";

const CONSISTENCY_HELP =
  "Average quarterly lead over the S&P 500 divided by how much that lead varies. Higher means the fund beat the index steadily rather than in one burst.";

const consistencyLabel = (value: number | null) => (value === null ? "—" : value.toFixed(2));

/**
 * The fund's return as a bar scaled to the best return on the board, with a
 * tick where the S&P 500 lands: distance from the tick is the lead or lag.
 */
function ReturnBar({ value, max, benchmark }: { value: number; max: number; benchmark: number }) {
  const scale = (v: number) => `${Math.min(100, Math.max(0, (v / max) * 100))}%`;
  return (
    <span aria-hidden="true" className="relative mt-1 block h-1 w-full bg-muted">
      <span
        className={cn(
          "absolute inset-y-0 left-0",
          value >= benchmark ? "bg-[hsl(var(--positive))]" : "bg-[hsl(var(--negative))]",
        )}
        style={{ width: scale(value) }}
      />
      <span
        className="absolute -inset-y-0.5 w-px bg-foreground/70"
        style={{ left: scale(benchmark) }}
      />
    </span>
  );
}

function PartialFlag({ fund, window }: { fund: RankedFund; window: number }) {
  if (!fund.partial) return null;
  const label = `Measured on ${fund.total} of ${window} quarters`;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          role="img"
          aria-label={label}
          className="inline-flex h-4 items-center rounded-sm border border-border px-1 text-[10px] leading-none text-muted-foreground"
        >
          {fund.total}/{window}Q
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-[260px] text-xs font-normal leading-relaxed">
        {label}: a quarter whose starting 13F held no measurable long equity (for example options
        only) has no return. Its return covers a shorter window; the S&amp;P 500 comparison uses the
        same quarters.
      </TooltipContent>
    </Tooltip>
  );
}

function CoverageFlag({ fund }: { fund: RankedFund }) {
  if (!fund.lowCoverage) return null;
  const share = `${(fund.maxUnpriced * 100).toFixed(0)}%`;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          role="img"
          aria-label={`Low price coverage: up to ${share} of the book unpriced in a quarter`}
          className="inline-flex text-amber-500"
        >
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-[260px] text-xs font-normal leading-relaxed">
        Up to {share} of the starting book could not be priced in one quarter and counts as flat, so
        this estimate is less reliable.
      </TooltipContent>
    </Tooltip>
  );
}

export default function FundRanking() {
  usePageMeta({
    title: RANKING_PAGE.title,
    description: RANKING_PAGE.description,
    canonical: canonicalUrl(RANKING_PAGE.path),
  });

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["fundRanking"],
    queryFn: async () => rankFunds(await getFundPerformanceRows()),
    staleTime: 10 * 60 * 1000,
  });
  const { sortKey, sortDir, columnSort } = useSortState<RankingKey>("cumReturn");

  const ranking = data;
  const funds = ranking ? sortRanking(ranking.funds, sortKey, sortDir) : [];
  const best = Math.max(...(ranking?.funds.map((f) => f.cumReturn) ?? [0]), 0.0001);
  const ahead = ranking?.funds.filter((f) => f.excess > 0).length ?? 0;
  const first = ranking?.startQuarter ?? "";
  const last = ranking?.quarters.at(-1) ?? "";
  const benchmark = ranking?.benchmarkReturn ?? 0;
  const windowSize = ranking?.quarters.length ?? 0;
  const partialCount = ranking?.funds.filter((f) => f.partial).length ?? 0;

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div>
        <h1 className="page-title">
          <Trophy aria-hidden="true" className="h-5 w-5 text-muted-foreground" />
          {RANKING_PAGE.heading}
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">
          Every tracked fund on the same quarters, by the estimated return of its 13F holdings
          against the S&amp;P 500.
        </p>
      </div>

      {isError ? (
        <QueryState isError error={error} title="Could not load fund performance" />
      ) : isLoading ? (
        <LoadingState message="Loading ranking…" />
      ) : !ranking || ranking.funds.length === 0 ? (
        <EmptyState padding="sm" title="No fund has an estimate for every quarter yet." />
      ) : (
        <>
          <div className="frame overflow-hidden">
            <div className="frame-title frame-title--spaced">
              <PanelTitle>
                {first} → {last}
              </PanelTitle>
            </div>

            <div className="hidden md:block">
              <TableFrame label="Fund ranking">
                <table className="w-full text-sm" aria-label="Fund ranking">
                  <thead>
                    <tr>
                      <th
                        scope="col"
                        className="w-10 px-3 py-2 text-right text-xs font-normal text-muted-foreground"
                      >
                        #
                      </th>
                      <ColumnHeader label="Fund" />
                      <ColumnHeader
                        label="Return"
                        align="right"
                        sort={columnSort("cumReturn")}
                        className="w-56"
                      />
                      <ColumnHeader label="vs S&P 500" align="right" sort={columnSort("excess")} />
                      <ColumnHeader
                        label="Quarters ahead"
                        align="right"
                        sort={columnSort("beats")}
                      />
                      <ColumnHeader
                        label="Worst quarter"
                        align="right"
                        sort={columnSort("worstQuarter")}
                      />
                      <ColumnHeader
                        label="Consistency"
                        align="right"
                        tooltip={CONSISTENCY_HELP}
                        sort={columnSort("consistency")}
                      />
                    </tr>
                  </thead>
                  <tbody className="tabular-nums">
                    {funds.map((f, i) => (
                      <tr key={f.fund} className="data-table-row">
                        <td className="px-3 py-1.5 text-right text-muted-foreground">{i + 1}</td>
                        <td className="px-3 py-1.5">
                          <span className="inline-flex items-center gap-1.5">
                            <FundCell fundName={f.fund} />
                            <PartialFlag fund={f} window={windowSize} />
                            <CoverageFlag fund={f} />
                          </span>
                        </td>
                        <td className={cn("px-3 py-1.5 text-right", toneClass(f.cumReturn))}>
                          {pctFrac(f.cumReturn)}
                          <ReturnBar value={f.cumReturn} max={best} benchmark={benchmark} />
                        </td>
                        <td className={cn("px-3 py-1.5 text-right", toneClass(f.excess))}>
                          {pctFrac(f.excess)}
                        </td>
                        <td className="px-3 py-1.5 text-right text-muted-foreground">
                          {f.beats}/{f.total}
                        </td>
                        <td className={cn("px-3 py-1.5 text-right", toneClass(f.worstQuarter))}>
                          {pctFrac(f.worstQuarter)}
                        </td>
                        <td className="px-3 py-1.5 text-right">
                          {consistencyLabel(f.consistency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableFrame>
            </div>

            <ol className="md:hidden divide-y divide-border" aria-label="Fund ranking cards">
              {funds.map((f, i) => (
                <li key={f.fund} className="px-3 py-3">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="inline-flex min-w-0 items-center gap-2">
                      <span className="w-6 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
                        {i + 1}
                      </span>
                      <FundCell fundName={f.fund} />
                      <PartialFlag fund={f} window={windowSize} />
                      <CoverageFlag fund={f} />
                    </span>
                    <span
                      className={cn("text-base font-medium tabular-nums", toneClass(f.cumReturn))}
                    >
                      {pctFrac(f.cumReturn)}
                    </span>
                  </div>
                  <ReturnBar value={f.cumReturn} max={best} benchmark={benchmark} />
                  <dl className="mt-2 grid grid-cols-4 gap-2 text-xs tabular-nums">
                    <div>
                      <dt className="text-muted-foreground">vs S&amp;P</dt>
                      <dd className={toneClass(f.excess)}>{pctFrac(f.excess)}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Ahead</dt>
                      <dd>
                        {f.beats}/{f.total}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Worst Q</dt>
                      <dd className={toneClass(f.worstQuarter)}>{pctFrac(f.worstQuarter)}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Consist.</dt>
                      <dd>{consistencyLabel(f.consistency)}</dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ol>
          </div>

          <p className="status-line border-t border-border pt-3 text-muted-foreground">
            S&amp;P 500 <span className={toneClass(benchmark)}>{pctFrac(benchmark)}</span> over{" "}
            {ranking.quarters.length} quarters; {ahead} of {ranking.funds.length} funds ahead of it.
            {partialCount > 0 &&
              ` ${partialCount} fund${partialCount === 1 ? "" : "s"} measured on fewer quarters, marked; compare those on the S&P 500 column.`}{" "}
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
              <TooltipContent className="max-w-[320px] text-xs font-normal leading-relaxed">
                Each quarter starts from the fund's 13F book (top 100 positions) and prices it to
                the next quarter end: no dividends, fees, shorts, options or trades inside the
                quarter. The funds were selected for their track record and the window spans a
                single rising market, so beating the index is partly selection and market, not only
                skill.
              </TooltipContent>
            </Tooltip>{" "}
            <span aria-hidden="true">·</span> Estimates, not investment advice
          </p>
        </>
      )}
    </div>
  );
}
