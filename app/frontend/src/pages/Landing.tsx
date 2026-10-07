import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { ArrowRight, Code2, Layers, Trophy, type LucideIcon } from "lucide-react";

import { CompanyLogo } from "@/components/CompanyLogo";
import GlobalSearch from "@/components/GlobalSearch";
import { FundLogo } from "@/components/FundLogo";
import { GitHubMark } from "@/components/GitHubMark";
import { PanelTitle } from "@/components/ui/PanelTitle";
import { STRETCHED_CARD, STRETCHED_LINK } from "@/components/ui/stretchedLink";
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

// Ordered fastest → slowest. `days` is calendar days and drives a shared-scale
// bar, so the eye reads "how long until this filing is public": Form 4 a sliver,
// 13F nearly full. The 13D row is the rule's five *business* days placed on that
// calendar scale; 13G is deliberately absent, since a Qualified Institutional
// Investor's is due 45 days after quarter end and would not be a faster filing.
const FRESHNESS = [
  { tag: "Form 4", label: "Insider trades", days: 2, lag: "2 bus. days", bar: "bg-positive" },
  { tag: "13D", label: "Ownership changes", days: 7, lag: "5 bus. days", bar: "bg-primary" },
  { tag: "13F", label: "Quarterly snapshot", days: 45, lag: "45 days", bar: "bg-warning" },
];
const MAX_LAG = 45;

const WIRE_ROWS = 8;

type FeatureLink = { to: string } | { href: string };

const FEATURES: { icon: LucideIcon; title: string; body: string; link: FeatureLink }[] = [
  {
    icon: Trophy,
    title: "A roster picked by track record",
    body: "Not the household names. Funds enter the list on measured performance, and the method is one click away.",
    link: { to: learnItem("how-funds-are-selected") },
  },
  {
    icon: Layers,
    title: "Three filing types, one timeline",
    body: "Form 4 and 13D/G land on top of the quarterly 13F, so consensus reflects what funds are doing now.",
    link: { to: ROUTES.latest },
  },
  {
    icon: Code2,
    title: "Source available, runs in your browser",
    body: "FastAPI and React, with the code public on GitHub. This site computes every consensus screen in your browser from the published filings, no backend needed.",
    link: { href: "https://github.com/dokson/hedge-fund-tracker" },
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
            <span className="text-xs text-muted-foreground tabular-nums">
              {f.filingDate.slice(5)}
            </span>
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

/** A headline number over its label, one cell of the stats strip. */
function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="flex flex-col items-center gap-1 px-4 py-5">
      <span className="text-[28px] font-semibold leading-8 tracking-[-0.03em] text-foreground tabular-nums">
        {value}
      </span>
      <span className="text-xs text-muted-foreground">{label}</span>
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
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-12 pb-4 sm:gap-16">
      <section className="flex flex-col items-center pt-6 text-center sm:pt-12">
        <Link
          to={ROUTES.latest}
          className="tap-target mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-card py-1 pl-2.5 pr-3 text-xs text-muted-foreground shadow-sm transition-colors duration-[120ms] hover:text-foreground"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-positive" aria-hidden="true" />
          <span>
            Data as of <span className="font-medium text-foreground">{asOf}</span> · SEC EDGAR
          </span>
          <ArrowRight className="h-3 w-3" aria-hidden="true" />
        </Link>
        <BrandLogo
          size={112}
          alt="Hedge Fund Tracker"
          priority
          className="mb-4 h-24 w-24 object-contain sm:h-28 sm:w-28"
        />
        <h1 className="max-w-[24ch] text-[clamp(2rem,5vw,3.5rem)] font-semibold leading-[1.05] tracking-[-0.035em] text-foreground">
          No Buffett. No Burry.{" "}
          <span className="block text-muted-foreground">Only the best track records.</span>
        </h1>
        <p className="mt-5 max-w-[58ch] text-[15px] leading-6 text-muted-foreground">
          SEC filings from a roster of funds selected by measured performance, turned into
          portfolios, deltas and consensus you can read in seconds.
        </p>
        <div className="mt-6 w-full max-w-md md:hidden">
          <GlobalSearch />
        </div>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            to={ROUTES.latest}
            className="inline-flex h-11 md:h-10 items-center gap-2 rounded-lg bg-primary px-5 text-sm font-medium text-primary-foreground shadow-sm transition-[filter] duration-[120ms] hover:brightness-110"
          >
            Open the board <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
          <a
            href="https://github.com/dokson/hedge-fund-tracker"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-11 md:h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-5 text-sm font-medium text-foreground shadow-sm transition-colors duration-[120ms] hover:bg-muted"
          >
            <GitHubMark className="h-4 w-4" /> Source
          </a>
        </div>
      </section>

      <section
        aria-label="At a glance"
        className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border shadow-sm sm:grid-cols-3"
      >
        <div className="bg-card">
          <Stat value={funds.length || "…"} label="Funds tracked" />
        </div>
        <div className="bg-card">
          <Stat value={tickers ? tickers.toLocaleString("en-US") : "…"} label="Tickers" />
        </div>
        <div className="col-span-2 bg-card sm:col-span-1">
          <Stat value={asOf} label="Latest quarter" />
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {FEATURES.map((f) => (
          <div
            key={f.title}
            className={cn(
              STRETCHED_CARD,
              "rounded-xl border border-border bg-card p-5 shadow-sm transition-[border-color,box-shadow] duration-[120ms] hover:border-input hover:shadow-md",
            )}
          >
            <div className="mb-4 grid h-9 w-9 place-items-center rounded-lg border border-border bg-muted text-primary-text">
              <f.icon className="h-4 w-4" aria-hidden="true" />
            </div>
            <h2 className="text-sm font-semibold text-foreground">
              {"to" in f.link ? (
                <Link to={f.link.to} className={STRETCHED_LINK}>
                  {f.title}
                </Link>
              ) : (
                <a
                  href={f.link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={STRETCHED_LINK}
                >
                  {f.title}
                </a>
              )}
            </h2>
            <p className="mt-1.5 text-[13px] leading-5 text-muted-foreground">{f.body}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:gap-6">
        <Wire funds={funds} />
        <div className="flex flex-col gap-4">
          <div className="frame">
            <div className="frame-title">
              <PanelTitle level={2}>A consensus that is current</PanelTitle>
              <span className="text-xs text-muted-foreground">Time to public</span>
            </div>
            <div className="space-y-3 p-3">
              {FRESHNESS.map((f) => (
                <div
                  key={f.tag}
                  className="grid grid-cols-[7ch_minmax(0,1fr)_11ch] items-center gap-3 text-[13px]"
                >
                  <span className="font-medium text-foreground">{f.tag}</span>
                  <div className="h-2 rounded-full bg-muted" aria-hidden="true">
                    <div
                      className={cn("h-full rounded-full", f.bar)}
                      style={{ width: `${(f.days / MAX_LAG) * 100}%` }}
                    />
                  </div>
                  <span className="text-right text-muted-foreground tabular-nums">{f.lag}</span>
                  <span className="sr-only">{f.label}</span>
                </div>
              ))}
              <p className="border-t border-border pt-3 text-xs leading-5 text-muted-foreground">
                Each bar is the delay until that filing becomes public, on a calendar-day scale.
                Form 4 and Schedule 13D land on top of the 45-day-old 13F. A Schedule 13G can be
                just as fast, but a large institution's is due 45 days after quarter end, the same
                lag as a 13F.
              </p>
            </div>
          </div>
          <p className="px-1 text-[13px] leading-5 text-muted-foreground">
            Most 13F trackers show holdings that are 45 or more days stale. The faster filings are
            stacked on top of the quarterly snapshot, so the picture reflects what funds are doing
            now.{" "}
            <Link to={learnItem("how-funds-are-selected")} className="tap-target ticker-link">
              How funds are selected
            </Link>
          </p>
        </div>
      </section>

      <footer className="status-note flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-4">
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
        <span>Data from SEC EDGAR</span>
        <span>Not investment advice</span>
      </footer>
    </div>
  );
}
