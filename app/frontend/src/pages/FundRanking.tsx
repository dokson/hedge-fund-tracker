import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Trophy } from "lucide-react";
import { Link } from "react-router";

import { FundCell } from "@/components/EntityLinks";
import { ColumnHeader } from "@/components/ui/ColumnHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
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
import { pctFrac, pp, toneClass } from "@/lib/performanceFormat";
import { learnItem } from "@/lib/routes";
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
        <button
          type="button"
          aria-label={label}
          className="-my-1 inline-flex min-h-7 shrink-0 cursor-help items-center rounded-sm border border-border px-1.5 text-[10px] leading-none text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {fund.total}/{window}Q
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-[260px] text-xs font-normal leading-relaxed">
        {label}: a missing quarter or a starting 13F with no measurable long equity has no return.
        These are fewer observed quarters, not necessarily consecutive. The S&amp;P 500 excess
        comparison uses only those same quarters.
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
        <button
          type="button"
          aria-label={`Low price coverage: up to ${share} of the book unpriced in a quarter`}
          className="-my-1 inline-flex min-h-7 min-w-7 shrink-0 cursor-help items-center justify-center rounded-sm text-warning hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
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
  const { sortKey, sortDir, columnSort } = useSortState<RankingKey>("cumReturn", "desc", "ranking");

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
          Estimated cumulative returns of tracked funds' 13F holdings against the S&amp;P 500, not
          certified fund returns.
        </p>
      </div>

      {isError ? (
        <QueryState isError error={error} title="Could not load fund performance" />
      ) : isLoading ? (
        <LoadingState message="Loading ranking…" />
      ) : !ranking || ranking.funds.length === 0 ? (
        <EmptyState padding="sm" title="No fund has a measurable return estimate yet." />
      ) : (
        <>
          <div className="space-y-2 border-y border-border py-3 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">
              {first} → {last} · {windowSize} observed quarter{windowSize === 1 ? "" : "s"}
            </p>
            <p className="max-w-3xl">
              {partialCount > 0
                ? `${partialCount} of ${ranking.funds.length} funds have partial windows; compare their excess (pp) over the same observed quarters. `
                : "All funds have estimates for the full window. "}
              A short sample from a roster selected on past performance does not establish skill.{" "}
              <Link
                to={learnItem("how-funds-are-selected")}
                className="text-primary-text hover:underline underline-offset-4"
              >
                Fund selection
              </Link>
              <span className="ml-2 inline-flex items-center gap-1 align-middle">
                <InfoTooltip text="Each estimate prices the starting 13F book (top 100 positions) to the next quarter end. It excludes dividends, fees, shorts, options and trades within the quarter. Unpriced holdings count as flat. Partial windows need not be consecutive." />
              </span>
            </p>
          </div>
          <div className="frame overflow-hidden">
            <div className="frame-title frame-title--spaced">
              <PanelTitle>Estimated cumulative return</PanelTitle>
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
                        label="Est. return"
                        align="right"
                        sort={columnSort("cumReturn")}
                        className="w-56"
                      />
                      <ColumnHeader
                        label="vs S&P 500 (pp)"
                        align="right"
                        sort={columnSort("excess")}
                      />
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
                          <span className="flex min-w-0 items-center gap-1.5">
                            <FundCell
                              fundName={f.fund}
                              className="min-w-0 [&>span>span:first-child]:whitespace-normal [&>span>span:first-child]:leading-4"
                            />
                            <PartialFlag fund={f} window={windowSize} />
                            <CoverageFlag fund={f} />
                          </span>
                        </td>
                        <td className={cn("px-3 py-1.5 text-right", toneClass(f.cumReturn))}>
                          {pctFrac(f.cumReturn)}
                          <ReturnBar
                            value={f.cumReturn}
                            max={best}
                            benchmark={f.cumReturn - f.excess}
                          />
                        </td>
                        <td className={cn("px-3 py-1.5 text-right", toneClass(f.excess))}>
                          {pp(f.excess * 100)}
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
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="w-6 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
                      {i + 1}
                    </span>
                    <FundCell
                      fundName={f.fund}
                      className="flex-1 text-sm [&>span>span:first-child]:line-clamp-2 [&>span>span:first-child]:whitespace-normal [&>span>span:first-child]:leading-4"
                    />
                    <PartialFlag fund={f} window={windowSize} />
                    <CoverageFlag fund={f} />
                  </div>
                  <div className="mt-2 text-right">
                    <span
                      className={cn(
                        "whitespace-nowrap text-base font-medium tabular-nums",
                        toneClass(f.cumReturn),
                      )}
                    >
                      {pctFrac(f.cumReturn)}
                    </span>
                  </div>
                  <ReturnBar value={f.cumReturn} max={best} benchmark={f.cumReturn - f.excess} />
                  <dl className="mt-2 grid grid-cols-4 gap-2 text-xs tabular-nums">
                    <div>
                      <dt className="text-muted-foreground">vs S&amp;P</dt>
                      <dd className={toneClass(f.excess)}>{pp(f.excess * 100)}</dd>
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
            {ranking.quarters.length} quarters; {ahead} of {ranking.funds.length} funds ahead on
            their observed quarters.
          </p>
        </>
      )}
    </div>
  );
}
