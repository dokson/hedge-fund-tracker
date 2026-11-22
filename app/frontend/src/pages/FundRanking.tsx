import { useId, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Trophy } from "lucide-react";

import { FundCell } from "@/components/EntityLinks";
import { CurveSpark } from "@/components/CurveSpark";
import { ColumnHeader } from "@/components/ui/ColumnHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { LoadingState } from "@/components/ui/LoadingState";
import { Panel } from "@/components/ui/Panel";
import { PageHeader } from "@/components/ui/PageHeader";
import { FaqLink, MetaLine } from "@/components/ui/TextLink";
import { QueryState } from "@/components/ui/QueryState";
import { ResponsiveTable } from "@/components/ui/ResponsiveTable";
import { CardSortBar } from "@/components/ui/CardSortBar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useResearchState } from "@/hooks/useResearchState";
import { useSortState } from "@/hooks/useSortState";
import { useFundRanking } from "@/hooks/useFundRanking";
import {
  formatValue,
  getAvailableQuarters,
  getQuarterFundList,
  getFundQuarterlyHoldings,
} from "@/lib/dataService";
import { fundNameToFileName } from "@/lib/data/funds";
import { HttpError } from "@/lib/data/fetch";
import {
  MIN_ANNUALIZED_QUARTERS,
  portfolioStats,
  sortRanking,
  type PortfolioStats,
  type RankedFund,
  type RankingKey,
} from "@/lib/fundRanking";
import { RANKING_PAGE } from "@/lib/pageMeta";
import { pctFrac, pp } from "@/lib/performanceFormat";
import { toneClass } from "@/lib/tone";
import { canonicalUrl } from "@/lib/seo";
import { cn } from "@/lib/utils";

const CONSISTENCY_HELP =
  "Average quarterly lead over the S&P 500 divided by how much that lead varies. Higher means the fund beat the index steadily rather than in one burst.";

const ANNUAL_HELP = `The cumulative estimate spread evenly over the fund's observed quarters, (1 + cumulative)^(4 / quarters) - 1, so funds with records of different length compare on one scale. Funds observed for fewer than ${MIN_ANNUALIZED_QUARTERS} quarters have no per-year figure and rank last.`;

const VOLATILITY_HELP = `How much the quarterly returns swing, as a yearly figure (their deviation times 2). Needs ${MIN_ANNUALIZED_QUARTERS} quarters.`;

const DRAWDOWN_HELP =
  "The deepest fall from a previous high of the cumulative estimate, counted from the starting book, on quarter-end values only.";

const TURNOVER_HELP =
  "The smaller of the quarter's buys and sales at reporting prices, over the book: the share of the portfolio replaced. A fund's first filing has no turnover.";

const LAST_QUARTER_HELP =
  "The estimate for the window's last quarter, with the lead over the S&P 500 below it. Empty when the fund has no estimate for that quarter.";

type RankingTab = "returns" | "risk" | "portfolio";

/** The measure each tab ranks by when it opens; its column leads the tab. */
const TAB_SORT: Record<RankingTab, RankingKey> = {
  returns: "annualReturn",
  risk: "consistency",
  portfolio: "aum",
};

const share = (value: number) => `${(value * 100).toFixed(1)}%`;
const orDash = (value: number | null | undefined, format: (v: number) => string) =>
  value == null ? "—" : format(value);

interface Column {
  label: string;
  /** Short label for the phone cards. */
  short: string;
  sortKey?: RankingKey;
  tooltip?: string;
  cell: (fund: RankedFund) => ReactNode;
  tone?: (fund: RankedFund) => string;
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
          className="-my-1 inline-flex min-h-7 shrink-0 cursor-help items-center rounded-sm border border-border px-1.5 text-[11px] leading-none text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
  const pct = `${(fund.maxUnpriced * 100).toFixed(0)}%`;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={`Low price coverage: up to ${pct} of the book unpriced in a quarter`}
          className="-my-1 inline-flex min-h-7 min-w-7 shrink-0 cursor-help items-center justify-center rounded-sm text-warning hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-[260px] text-xs font-normal leading-relaxed">
        Up to {pct} of the starting book could not be priced in one quarter and counts as flat, so
        this estimate is less reliable.
      </TooltipContent>
    </Tooltip>
  );
}

/**
 * Each tab's columns after the fund. The tab's own measure leads, in medium weight, and is
 * what the tab ranks by (`TAB_SORT`); %/yr follows on the other tabs as the shared reference.
 */
function tabColumns(tab: RankingTab, lastQuarter: string): Column[] {
  const annual: Column = {
    label: "%/yr",
    short: "%/yr",
    sortKey: "annualReturn",
    tooltip: ANNUAL_HELP,
    cell: (f) => orDash(f.annualReturn, pctFrac),
    tone: (f) =>
      cn(
        "font-medium",
        f.annualReturn === null ? "text-muted-foreground" : toneClass(f.annualReturn),
      ),
  };
  if (tab === "returns") {
    return [
      annual,
      {
        label: "Path vs benchmarks",
        short: "Path",
        cell: (f) => <CurveSpark curve={f.curve} />,
      },
      {
        label: "Cumulative",
        short: "Cumulative",
        sortKey: "cumReturn",
        cell: (f) => pctFrac(f.cumReturn),
        tone: (f) => toneClass(f.cumReturn),
      },
      {
        label: "vs Nasdaq-100 (pp)",
        short: "vs NDX",
        sortKey: "excessNasdaq",
        cell: (f) => orDash(f.excessNasdaq, (v) => pp(v * 100)),
        tone: (f) =>
          f.excessNasdaq === null ? "text-muted-foreground" : toneClass(f.excessNasdaq),
      },
      {
        label: "vs S&P 500 (pp)",
        short: "vs S&P",
        sortKey: "excess",
        cell: (f) => pp(f.excess * 100),
        tone: (f) => toneClass(f.excess),
      },
      {
        label: lastQuarter,
        short: lastQuarter,
        sortKey: "lastReturn",
        tooltip: LAST_QUARTER_HELP,
        cell: (f) =>
          f.lastReturn === null ? (
            "—"
          ) : (
            <span className="inline-flex flex-col items-end leading-5">
              <span className={toneClass(f.lastReturn)}>{pctFrac(f.lastReturn)}</span>
              {f.lastExcess !== null && (
                <span className={cn("text-xs", toneClass(f.lastExcess))}>
                  {pp(f.lastExcess * 100)}
                </span>
              )}
            </span>
          ),
      },
    ];
  }
  if (tab === "risk") {
    return [
      {
        label: "Consistency",
        short: "Consist.",
        sortKey: "consistency",
        tooltip: CONSISTENCY_HELP,
        cell: (f) => orDash(f.consistency, (v) => v.toFixed(2)),
        tone: (f) =>
          cn("font-medium", f.consistency === null ? "text-muted-foreground" : "text-foreground"),
      },
      annual,
      {
        label: "Max drawdown",
        short: "Drawdown",
        sortKey: "maxDrawdown",
        tooltip: DRAWDOWN_HELP,
        cell: (f) => pctFrac(f.maxDrawdown),
        tone: (f) => toneClass(f.maxDrawdown),
      },
      {
        label: "Volatility",
        short: "Volatility",
        sortKey: "volatility",
        tooltip: VOLATILITY_HELP,
        cell: (f) => orDash(f.volatility, share),
      },
      {
        label: "Quarters ahead",
        short: "Ahead",
        sortKey: "beats",
        cell: (f) => `${f.beats}/${f.total}`,
        tone: () => "text-muted-foreground",
      },
    ];
  }
  return [
    {
      label: "AUM",
      short: "AUM",
      sortKey: "aum",
      cell: (f) => (f.aum === undefined ? "…" : orDash(f.aum, formatValue)),
      tone: (f) => cn("font-medium", f.aum == null ? "text-muted-foreground" : "text-foreground"),
    },
    annual,
    {
      label: "Positions",
      short: "Positions",
      sortKey: "positions",
      cell: (f) => (f.positions === undefined ? "…" : orDash(f.positions, String)),
    },
    {
      label: "Top 10 weight",
      short: "Top 10",
      sortKey: "top10Weight",
      cell: (f) => (f.top10Weight === undefined ? "…" : orDash(f.top10Weight, share)),
    },
    {
      label: "Turnover",
      short: "Turnover",
      sortKey: "turnover",
      tooltip: TURNOVER_HELP,
      cell: (f) => (f.turnover === undefined ? "…" : orDash(f.turnover, share)),
    },
    {
      label: "13F",
      short: "13F",
      cell: (f) => f.portfolioQuarter?.replace("Q", " Q") ?? "…",
      tone: () => "text-muted-foreground",
    },
  ];
}

/** Latest 13F book figures per fund, from each fund's newest filed quarter. */
async function loadPortfolios(
  funds: readonly string[],
): Promise<Map<string, PortfolioStats & { quarter: string }>> {
  const stats = new Map<string, PortfolioStats & { quarter: string }>();
  const quarters = await getAvailableQuarters();
  const manifests = await Promise.all(
    quarters.map(async (quarter) => {
      try {
        return await getQuarterFundList(quarter);
      } catch (error) {
        if (error instanceof HttpError && error.status === 404) return [];
        throw error;
      }
    }),
  );
  const latest = new Map<string, string>();
  quarters.forEach((quarter, index) => {
    for (const filename of manifests[index]) latest.set(filename, quarter);
  });
  await Promise.all(
    funds.map(async (fund) => {
      try {
        const quarter = latest.get(fundNameToFileName(fund));
        if (!quarter) return;
        stats.set(fund, {
          ...portfolioStats(await getFundQuarterlyHoldings(quarter, fund)),
          quarter,
        });
      } catch {
        // A fund whose book cannot load keeps empty portfolio cells; the rest still rank.
      }
    }),
  );
  return stats;
}

export default function FundRanking() {
  const captionId = useId();
  usePageMeta({
    title: RANKING_PAGE.title,
    description: RANKING_PAGE.description,
    canonical: canonicalUrl(RANKING_PAGE.path),
  });

  const { data, isLoading, isError, error } = useFundRanking();
  const [tab, setTab] = useResearchState<RankingTab>("tab", "returns");
  const { sortKey, sortDir, setSort, toggleSort, columnSort } = useSortState<RankingKey>(
    TAB_SORT.returns,
    "desc",
    "ranking",
  );
  // A tab is a question (who earned most, who earned it steadily, who holds what), so opening
  // one ranks by its own measure; a header click then re-sorts within it.
  const openTab = (next: RankingTab) => {
    setTab(next);
    setSort(TAB_SORT[next], "desc");
  };

  const ranking = data;
  const fundNames = ranking?.funds.map((f) => f.fund) ?? [];
  const {
    data: portfolios,
    isError: portfoliosFailed,
    error: portfoliosError,
  } = useQuery({
    queryKey: ["rankingPortfolios", fundNames.length],
    queryFn: () => loadPortfolios(fundNames),
    enabled: tab === "portfolio" && fundNames.length > 0,
    staleTime: 10 * 60 * 1000,
  });

  const withPortfolio = (ranking?.funds ?? []).map((f) => {
    if (!portfolios) return f;
    const p = portfolios.get(f.fund);
    return {
      ...f,
      aum: p?.aum ?? null,
      positions: p?.positions ?? null,
      top10Weight: p?.top10Weight ?? null,
      turnover: p?.turnover ?? null,
      portfolioQuarter: p?.quarter,
    };
  });
  const funds = sortRanking(withPortfolio, sortKey, sortDir);
  const ahead = ranking?.funds.filter((f) => f.excess > 0).length ?? 0;
  const first = ranking?.startQuarter ?? "";
  const last = ranking?.quarters.at(-1) ?? "";
  const lastLabel = last.replace("Q", " Q");
  const benchmark = ranking?.benchmarkReturn ?? 0;
  const windowSize = ranking?.quarters.length ?? 0;
  const partialCount = ranking?.funds.filter((f) => f.partial).length ?? 0;

  const board = (current: RankingTab) => {
    const columns = tabColumns(current, lastLabel);
    const caption = `${current[0].toUpperCase()}${current.slice(1)} fund ranking`;
    return (
      <ResponsiveTable
        singleLayout
        label={caption}
        labelledBy={`${captionId}-${current}`}
        table={
          <table className="w-full text-sm">
            <caption id={`${captionId}-${current}`} className="sr-only">
              {caption}
            </caption>
            <thead>
              <tr>
                <th
                  scope="col"
                  className="w-10 px-3 py-2 text-right text-xs font-normal text-muted-foreground"
                >
                  #
                </th>
                <ColumnHeader label="Fund" />
                {columns.map((c) => (
                  <ColumnHeader
                    key={c.label}
                    label={c.label}
                    align="right"
                    tooltip={c.tooltip}
                    sort={c.sortKey ? columnSort(c.sortKey) : undefined}
                  />
                ))}
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {funds.map((f, i) => (
                <tr key={f.fund} className="data-table-row">
                  <td className="px-3 py-1.5 text-right text-muted-foreground">{i + 1}</td>
                  <th scope="row" className="px-3 py-1.5 text-left font-normal">
                    <span className="flex min-w-0 items-center gap-1.5">
                      <FundCell
                        fundName={f.fund}
                        className="min-w-0 [&>span>span:first-child]:whitespace-normal [&>span>span:first-child]:leading-4"
                      />
                      <PartialFlag fund={f} window={windowSize} />
                      <CoverageFlag fund={f} />
                    </span>
                  </th>
                  {columns.map((c) => (
                    <td
                      key={c.label}
                      className={cn("whitespace-nowrap px-3 py-1.5 text-right", c.tone?.(f))}
                    >
                      {c.cell(f)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        }
        cards={
          <div className="space-y-3">
            {/* The cards have no headers: the tab's sortable columns become a sort bar. */}
            <CardSortBar
              options={columns.flatMap((c) =>
                c.sortKey ? [{ key: c.sortKey, label: c.short }] : [],
              )}
              sortKey={sortKey}
              sortDir={sortDir}
              onToggle={toggleSort}
            />
            {/* Explicit role: Safari drops list semantics under `list-style: none`. */}
            <ol
              // oxlint-disable-next-line jsx-a11y/no-redundant-roles
              role="list"
              className="divide-y divide-border"
              aria-label="Fund ranking cards"
            >
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
                  <div className="mt-2 text-right tabular-nums">
                    <span className="mr-2 text-xs text-muted-foreground">{columns[0].label}</span>
                    <span
                      className={cn(
                        "whitespace-nowrap text-base font-medium",
                        columns[0].tone?.(f),
                      )}
                    >
                      {columns[0].cell(f)}
                    </span>
                  </div>
                  <dl className="mt-2 grid grid-cols-3 gap-2 text-xs tabular-nums">
                    {columns.slice(1).map((c) => (
                      <div key={c.label} className="min-w-0">
                        <dt className="text-muted-foreground">{c.short}</dt>
                        <dd className={c.tone?.(f)}>{c.cell(f)}</dd>
                      </div>
                    ))}
                  </dl>
                </li>
              ))}
            </ol>
          </div>
        }
      />
    );
  };

  const panelTitle: Record<RankingTab, string> = {
    returns: "Who earned the most per year",
    risk: "Who led the S&P 500 steadily, and how deep they fell",
    portfolio: "Who manages the most, and how concentrated they are",
  };

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <PageHeader
        title={RANKING_PAGE.heading}
        icon={Trophy}
        description="Estimated returns per year of tracked funds' 13F holdings against the S&P 500, not certified fund returns."
      />

      {isError ? (
        <QueryState isError error={error} title="Could not load fund performance" />
      ) : isLoading ? (
        <LoadingState message="Loading ranking…" />
      ) : !ranking || ranking.funds.length === 0 ? (
        <EmptyState padding="sm" title="No fund has a measurable return estimate yet." />
      ) : (
        <>
          <MetaLine className="-mt-3 block leading-5">
            <span className="font-medium text-foreground">
              {first} to {last}, {windowSize} observed quarter
              {windowSize === 1 ? "" : "s"}.
            </span>{" "}
            {partialCount > 0
              ? `${partialCount} of ${ranking.funds.length} funds have partial windows: compare their return per year or their excess over the same quarters. `
              : "All funds have estimates for the full window. "}
            A short sample from a roster selected on past performance does not establish skill.{" "}
            <FaqLink item="how-funds-are-selected">Fund selection</FaqLink>
            <span className="ml-1.5 inline-flex align-middle">
              <InfoTooltip text="Each estimate prices the starting 13F book (top 100 positions) to the next quarter end. It excludes dividends, fees, shorts, options and trades within the quarter. Unpriced holdings count as flat. Partial windows need not be consecutive." />
            </span>
          </MetaLine>
          <Tabs value={tab} onValueChange={(v) => openTab(v as RankingTab)}>
            <TabsList aria-label="Ranking views">
              <TabsTrigger value="returns">Returns</TabsTrigger>
              <TabsTrigger value="risk">Risk</TabsTrigger>
              <TabsTrigger value="portfolio">Portfolio</TabsTrigger>
            </TabsList>
            {(["returns", "risk", "portfolio"] as const).map((t) => (
              // Findable: find in page reaches a fund in any tab and opens that tab.
              <TabsContent key={t} value={t} className="mt-4" findable>
                <Panel
                  title={panelTitle[t]}
                  spaced
                  headerClassName="h-auto min-h-10 py-2 [&>h2]:whitespace-normal"
                >
                  {t === "portfolio" && portfoliosFailed ? (
                    <QueryState
                      isError
                      error={portfoliosError}
                      title="Could not load the funds' latest 13F books"
                      className="border-0"
                    />
                  ) : (
                    board(t)
                  )}
                </Panel>
              </TabsContent>
            ))}
          </Tabs>

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
