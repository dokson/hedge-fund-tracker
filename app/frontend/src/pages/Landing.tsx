import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { ArrowRight } from "lucide-react";

import { CompanyLogo } from "@/components/CompanyLogo";
import GlobalSearch from "@/components/GlobalSearch";
import { FundLogo } from "@/components/FundLogo";
import { GitHubMark } from "@/components/GitHubMark";
import { PanelTitle } from "@/components/ui/PanelTitle";
import { QueryState } from "@/components/ui/QueryState";
import { getHedgeFunds, getStocks, type HedgeFund } from "@/lib/dataService";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { useEnrichedNQFilings } from "@/hooks/useEnrichedNQFilings";
import { usePageMeta } from "@/hooks/usePageMeta";
import { HOME_PAGE } from "@/lib/pageMeta";
import { ROUTES, fundPath, learnItem, stockPath } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";
import { cn } from "@/lib/utils";
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
  const rows = [...filings]
    .sort((a, b) => (b.filingDate > a.filingDate ? 1 : b.filingDate < a.filingDate ? -1 : 0))
    .slice(0, WIRE_ROWS);

  return (
    <div className="frame flex flex-col overflow-hidden">
      <div className="frame-title">
        <PanelTitle>Latest filings</PanelTitle>
        <Link
          to={ROUTES.latest}
          className="tap-target inline-flex items-center gap-1 text-[13px] font-normal text-primary-text hover:underline"
        >
          View all <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </div>
      <p className="border-b border-border px-3 py-2 text-xs leading-5 text-muted-foreground">
        Sorted by filing date. Reported positions may be dated earlier.
      </p>
      <ol className="divide-y divide-border/60">
        {isLoading &&
          Array.from({ length: WIRE_ROWS }, (_, i) => (
            <li key={i} className="h-10 flex items-center px-3">
              <span className="h-3 w-full max-w-64 animate-pulse rounded-full bg-muted" />
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
            className="grid grid-cols-[2.75rem_5.5rem_minmax(0,1fr)_auto] items-center gap-x-3 px-3 h-10 text-[13px] transition-colors duration-[120ms] hover:bg-muted/60"
          >
            <time
              dateTime={f.filingDate}
              title={`Filed ${f.filingDate}`}
              className="text-xs text-muted-foreground tabular-nums"
            >
              {f.filingDate.slice(5)}
            </time>
            <span className="flex min-w-0 items-center gap-2">
              <CompanyLogo ticker={f.ticker} size={20} />
              <Link to={stockPath(f.ticker)} className="ticker-link truncate">
                {f.ticker}
              </Link>
            </span>
            <span className="flex min-w-0 items-center gap-2">
              <FundLogo fundName={f.fund} url={urlByFund.get(f.fund)} size={16} />
              <Link to={fundPath(f.fund)} className="fund-link truncate">
                {f.fund}
              </Link>
            </span>
            <span
              className={cn(
                "chip",
                f.deltaType === "NEW" || f.deltaType === "INCREASE"
                  ? "text-positive"
                  : f.deltaType === "CLOSED" || f.deltaType === "DECREASE"
                    ? "text-negative"
                    : "text-muted-foreground",
              )}
            >
              {f.deltaType}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function Landing() {
  const { data: funds = [] } = useQuery({ queryKey: ["hedge_funds"], queryFn: getHedgeFunds });
  const { data: stocks = [] } = useQuery({ queryKey: ["stocks"], queryFn: getStocks });
  const { latestQuarter } = useAvailableQuarters();
  const tickers = new Set(stocks.map((s) => s.ticker)).size;
  const asOf = latestQuarter ? latestQuarter.replace("Q", " Q") : "…";

  usePageMeta({
    title: HOME_PAGE.title,
    description: HOME_PAGE.description,
    canonical: canonicalUrl(HOME_PAGE.path),
  });

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 pb-4 sm:gap-10">
      <section className="grid items-start gap-8 pt-3 sm:pt-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:gap-12">
        <div>
          <BrandLogo
            size={80}
            alt="Hedge Fund Tracker"
            priority
            className="mb-5 h-16 w-16 object-contain sm:h-20 sm:w-20"
          />
          <h1 className="max-w-[24ch] text-[clamp(2rem,4.5vw,3.25rem)] font-semibold leading-[1.08] tracking-[-0.035em] text-foreground">
            No Buffett. No Burry.{" "}
            <span className="block text-muted-foreground">Selected by measured performance.</span>
          </h1>
          <p className="mt-5 max-w-[58ch] text-[15px] leading-6 text-muted-foreground">
            Research the stocks tracked funds report owning. Compare quarterly conviction across
            funds, then examine the recent disclosures behind the changes.
          </p>
          <div className="mt-6 w-full max-w-md md:hidden">
            <GlobalSearch />
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Link
              to={ROUTES.quarterly}
              className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-[filter] duration-[120ms] hover:brightness-110"
            >
              Quarterly Trends <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            <Link
              to={ROUTES.latest}
              className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground transition-colors duration-[120ms] hover:bg-muted"
            >
              Latest Filings <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
        </div>

        <div className="border-y border-border py-5 lg:mt-2">
          <h2 className="text-base font-semibold text-foreground">
            Start with the quarterly snapshot
          </h2>
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
            <div className="col-span-2 flex flex-wrap items-baseline justify-between gap-2 border-b border-border pb-3">
              <dt className="text-muted-foreground">13F baseline</dt>
              <dd className="text-lg font-semibold text-foreground tabular-nums">{asOf}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Funds tracked</dt>
              <dd className="mt-1 font-medium text-foreground tabular-nums">
                {funds.length || "…"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Tickers in saved data</dt>
              <dd className="mt-1 font-medium text-foreground tabular-nums">
                {tickers ? tickers.toLocaleString("en-US") : "…"}
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-[13px] leading-5 text-muted-foreground">
            The baseline is a quarter-end holdings snapshot, not a date for every price or filing.
            13Fs are due up to 45 days after quarter end; other disclosures have different
            deadlines.
          </p>
          <Link
            to={learnItem("when-are-13f-due")}
            className="tap-target mt-2 inline-flex items-center gap-1 text-[13px] text-primary-text hover:underline"
          >
            Understand reporting delays <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </div>
      </section>

      <section className="grid items-start gap-8 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:gap-12">
        <Wire funds={funds} />
        <div>
          <h2 className="text-base font-semibold text-foreground">Read the evidence in context</h2>
          <ul className="mt-2 divide-y divide-border">
            {RESEARCH_CONTEXT.map((item) => (
              <li key={item.to} className="py-4">
                <h3 className="text-sm font-medium text-foreground">
                  <Link to={item.to} className="inline-flex items-start gap-2 hover:underline">
                    {item.title}
                    <ArrowRight
                      className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary-text"
                      aria-hidden="true"
                    />
                  </Link>
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
        <a
          href="https://github.com/dokson/hedge-fund-tracker"
          target="_blank"
          rel="noopener noreferrer"
          className="tap-target inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground hover:underline sm:ml-auto"
        >
          <GitHubMark className="h-3.5 w-3.5" /> Source repository
        </a>
      </footer>
    </div>
  );
}
