import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { ArrowRight } from "lucide-react";

import { TickerLink } from "@/components/EntityLinks";
import GlobalSearch from "@/components/GlobalSearch";
import { FundLogo } from "@/components/FundLogo";
import { GitHubLink } from "@/components/GitHubLink";
import { Panel } from "@/components/ui/Panel";
import { PageHeader } from "@/components/ui/PageHeader";
import { Stat, StatGrid } from "@/components/ui/Stat";
import { ChangeChip } from "@/components/ui/ChangeChip";
import { FaqLink, TextLink } from "@/components/ui/TextLink";
import { QueryState } from "@/components/ui/QueryState";
import { getHedgeFunds, getStocks, type HedgeFund } from "@/lib/dataService";
import { useFundRanking } from "@/hooks/useFundRanking";
import { pctFrac } from "@/lib/performanceFormat";
import { toneClass } from "@/lib/tone";
import { CurveSpark } from "@/components/CurveSpark";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { useEnrichedNQFilings } from "@/hooks/useEnrichedNQFilings";
import { usePageMeta } from "@/hooks/usePageMeta";
import { HOME_PAGE } from "@/lib/pageMeta";
import { ROUTES, fundPath, learnItem } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";
import { BrandLogo } from "@/components/ui/BrandLogo";

const WIRE_ROWS = 8;

const RESEARCH_CONTEXT = [
  {
    title: "A roster selected by measured performance",
    body: "Explore the selection method before comparing funds. A measured track record is a starting point for research, not a promise of future returns.",
    to: learnItem("how-funds-are-selected"),
  },
  {
    title: "Filing dates are not position dates",
    body: "Recent disclosures add to the quarterly baseline. Publication can follow the reported position date; these are disclosed holdings, not a live view of trading.",
    to: ROUTES.latest,
  },
  {
    title: "Reported holdings, not the whole portfolio",
    body: "13F snapshots omit shorts, cash and most non-U.S. holdings. Read the coverage limits before treating a position as a fund’s complete strategy.",
    to: learnItem("what-is-a-13f"),
  },
];

/** The newest filings on the wire, real data. */
function Wire({ funds }: { funds: readonly HedgeFund[] }) {
  const { data: filings = [], isLoading, isError, error } = useEnrichedNQFilings();
  const urlByFund = new Map(funds.map((f) => [f.fund, f.url]));
  const rows = filings
    .toSorted((a, b) => (b.filingDate > a.filingDate ? 1 : b.filingDate < a.filingDate ? -1 : 0))
    .slice(0, WIRE_ROWS);

  return (
    <Panel
      title="Latest filings"
      className="flex flex-col"
      aside={
        <TextLink to={ROUTES.latest} className="tap-target text-[13px]">
          View all <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </TextLink>
      }
    >
      <p className="border-b border-border px-3 py-2 text-xs leading-5 text-muted-foreground">
        Sorted by filing date. Reported positions may be dated earlier.
      </p>
      <ol className="divide-y divide-border/60">
        {isLoading &&
          Array.from({ length: WIRE_ROWS }, (_, i) => (
            <li key={i} className="h-10 flex items-center px-3">
              <span className="h-3 w-full max-w-64 animate-pulse motion-reduce:animate-none rounded-full bg-muted" />
            </li>
          ))}
        {isError && (
          <li>
            <QueryState
              isError
              error={error}
              title="Could not load the latest filings"
              className="rounded-none border-0 py-6 shadow-none"
            />
          </li>
        )}
        {!isLoading && !isError && rows.length === 0 && (
          <li className="px-3 py-3 text-[13px] text-muted-foreground">No filings yet.</li>
        )}
        {rows.map((f) => (
          <li
            key={`${f.fund}-${f.ticker}-${f.filingDate}`}
            // On a phone the ticker and the fund stack in one column (four columns left the fund
            // 0px wide at 320px); from `sm` they are columns of their own.
            className="grid grid-cols-[2.75rem_minmax(0,1fr)_auto] sm:grid-cols-[2.75rem_6.5rem_minmax(0,1fr)_auto] items-center gap-x-3 px-3 min-h-11 py-1 sm:py-0 text-[13px] transition-colors duration-[120ms] hover:bg-muted/60"
          >
            <time
              dateTime={f.filingDate}
              title={`Filed ${f.filingDate}`}
              className="text-xs text-muted-foreground tabular-nums"
            >
              {f.filingDate.slice(5)}
            </time>
            <span className="flex min-w-0 flex-col sm:contents">
              <TickerLink ticker={f.ticker} className="min-w-0" />
              <span className="flex min-w-0 items-center gap-2">
                <FundLogo fundName={f.fund} url={urlByFund.get(f.fund)} size={16} />
                <Link to={fundPath(f.fund)} className="fund-link truncate">
                  {f.fund}
                </Link>
              </span>
            </span>
            <ChangeChip change={f.deltaType} />
          </li>
        ))}
      </ol>
    </Panel>
  );
}

const TOP_FUNDS = 5;

/** The ranking's leaders by return per year, real data; quiet on failure (the wire reports errors). */
function TopFunds({ funds }: { funds: readonly HedgeFund[] }) {
  const { data, isLoading } = useFundRanking();
  const urlByFund = new Map(funds.map((f) => [f.fund, f.url]));
  const leaders = (data?.funds ?? []).filter((f) => f.annualReturn !== null).slice(0, TOP_FUNDS);
  return (
    <Panel
      title="Top funds by return per year"
      aside={
        <TextLink to={ROUTES.fundRanking} className="tap-target text-[13px]">
          Full ranking <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </TextLink>
      }
    >
      {/* Explicit role: Safari drops list semantics under `list-style: none`. */}
      {/* oxlint-disable-next-line jsx-a11y/no-redundant-roles */}
      <ol role="list" className="divide-y divide-border/60">
        {isLoading &&
          Array.from({ length: TOP_FUNDS }, (_, i) => (
            <li key={i} aria-hidden="true" className="flex h-9 items-center px-3">
              <span className="h-3 w-full rounded-full bg-muted animate-pulse motion-reduce:animate-none" />
            </li>
          ))}
        {!isLoading && leaders.length === 0 && (
          <li className="min-h-44 px-3 py-2 text-sm text-muted-foreground">
            No fund returns available.
          </li>
        )}
        {leaders.map((f, i) => (
          <li
            key={f.fund}
            // The path needs 6rem; on a phone it would squeeze the fund's name to nothing, so
            // there the row keeps the name and the figure.
            className="grid grid-cols-[1.25rem_minmax(0,1fr)_auto] sm:grid-cols-[1.25rem_minmax(0,1fr)_auto_6rem] items-center gap-x-3 px-3 py-2 text-[13px]"
          >
            <span className="text-right text-xs text-muted-foreground tabular-nums">{i + 1}</span>
            <span className="flex min-w-0 items-center gap-2">
              <FundLogo fundName={f.fund} url={urlByFund.get(f.fund)} size={16} />
              <Link to={fundPath(f.fund)} className="fund-link truncate">
                {f.fund}
              </Link>
            </span>
            <span className={`font-medium tabular-nums ${toneClass(f.annualReturn ?? 0)}`}>
              {pctFrac(f.annualReturn ?? 0)}/yr
            </span>
            <span className="hidden sm:block">
              <CurveSpark curve={f.curve} />
            </span>
          </li>
        ))}
      </ol>
      <p className="border-t border-border px-3 py-2 text-xs leading-5 text-muted-foreground">
        Estimated from reported 13F holdings against the S&amp;P 500, not certified returns.
      </p>
    </Panel>
  );
}

export default function Landing() {
  const { data: funds = [] } = useQuery({
    queryKey: ["hedge_funds"],
    queryFn: getHedgeFunds,
  });
  const { data: stocks = [] } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
  });
  const { latestQuarter } = useAvailableQuarters();
  const tickers = new Set(stocks.map((s) => s.ticker)).size;
  const asOf = latestQuarter ? latestQuarter.replace("Q", " Q") : "…";

  usePageMeta({
    title: HOME_PAGE.title,
    description: HOME_PAGE.description,
    canonical: canonicalUrl(HOME_PAGE.path),
  });

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 pb-4 sm:gap-14">
      <section className="grid items-center gap-8 pt-3 sm:pt-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:gap-12">
        <div>
          <BrandLogo
            size={80}
            alt="Hedge Fund Tracker"
            priority
            className="mb-5 h-16 w-16 object-contain sm:h-20 sm:w-20"
          />
          <PageHeader
            title={
              <span className="block max-w-[22ch] text-[clamp(2rem,4.5vw,3.25rem)] leading-[1.08] tracking-[-0.035em]">
                No Buffett. No Burry.
                <br />
                Selected by measured performance.
              </span>
            }
            description="Research what the tracked funds report owning, how their conviction moved, and the filings behind each change."
            className="space-y-5"
          />
          <div className="mt-6 w-full max-w-md md:hidden">
            <GlobalSearch />
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Link
              to={ROUTES.quarterly}
              className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors duration-[120ms] hover:bg-primary/90 active:bg-primary/80"
            >
              Quarterly Trends <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            <Link
              to={ROUTES.latest}
              className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground transition-colors duration-[120ms] hover:bg-muted active:bg-secondary"
            >
              Latest Filings <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
          <StatGrid className="mt-8 grid-cols-3">
            <Stat
              label="13F baseline"
              value={asOf}
              info="A quarter-end holdings snapshot, not a date for every price or filing. 13Fs are due up to 45 days after quarter end; other disclosures have different deadlines."
            />
            <Stat label="Funds tracked" value={funds.length || "…"} />
            <Stat label="Tickers" value={tickers ? tickers.toLocaleString("en-US") : "…"} />
          </StatGrid>
          <FaqLink item="when-are-13f-due" className="tap-target mt-2 text-[13px]">
            Understand reporting delays <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </FaqLink>
        </div>

        <TopFunds funds={funds} />
      </section>

      <section className="grid items-start gap-8 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:gap-12">
        <Wire funds={funds} />
        <div>
          <h2 className="text-base font-semibold text-foreground">Read the evidence in context</h2>
          <ul className="mt-2 divide-y divide-border">
            {RESEARCH_CONTEXT.map((item) => (
              <li key={item.to} className="py-4">
                <h3 className="text-sm font-medium text-foreground">
                  <TextLink to={item.to} className="items-start gap-2 text-foreground">
                    {item.title}
                    <ArrowRight
                      className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary-text"
                      aria-hidden="true"
                    />
                  </TextLink>
                </h3>
                <p className="mt-1.5 text-[13px] leading-5 text-muted-foreground">{item.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <footer className="status-note flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border pt-4">
        <span>
          Built by{" "}
          <a
            href="https://www.coalesce.coach/en"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="COalesCE website"
            className="tap-target text-foreground underline underline-offset-2"
          >
            COalesCE
          </a>
        </span>
        <span>Saved SEC EDGAR data</span>
        <span>Not investment advice</span>
        <GitHubLink className="sm:ml-auto" />
      </footer>
    </div>
  );
}
