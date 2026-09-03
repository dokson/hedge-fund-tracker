import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { GitHubMark } from "@/components/GitHubMark";
import { PanelTitle } from "@/components/ui/PanelTitle";
import { BASE_PATH } from "@/lib/config";
import { getEnrichedNQFilings, getHedgeFunds, getStocks } from "@/lib/dataService";
import { usePageMeta } from "@/hooks/usePageMeta";
import { ROUTES, fundPath, learnItem, stockPath } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";
import { cn } from "@/lib/utils";

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

// The wire fills whatever height the hero row leaves, so the panel bottoms out
// on the footer rule instead of leaving a void under it. The list is longer
// than the shortest viewport shows and the frame's `overflow-hidden` clips the
// remainder: no visible overflow, no scrollbar inside the hero.
const WIRE_ROWS = 16;

const FEATURES = [
  {
    title: "A roster picked by track record",
    body: "Not the household names. Funds enter the list on measured performance, and the method is one click away.",
  },
  {
    title: "Three filing types, one timeline",
    body: "Form 4 and 13D/G land on top of the quarterly 13F, so consensus reflects what funds are doing now.",
  },
  {
    title: "Open source, runs anywhere",
    body: "FastAPI and React, self-hostable, with a static demo in which every analysis feature works without a backend.",
  },
];

/** The newest filings on the wire: the hero's right column, real data. */
function Wire() {
  const { data: filings = [], isLoading } = useQuery({
    queryKey: ["enrichedNQFilings"],
    queryFn: () => getEnrichedNQFilings(),
  });
  const rows = [...filings]
    .sort((a, b) => (b.filingDate > a.filingDate ? 1 : b.filingDate < a.filingDate ? -1 : 0))
    .slice(0, WIRE_ROWS);

  return (
    <div className="frame flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="frame-title">
        <PanelTitle>Latest filings</PanelTitle>
        <Link
          to={ROUTES.latest}
          className="text-[13px] font-normal text-primary-text hover:underline"
        >
          View all
        </Link>
      </div>
      <ol className="flex-1 divide-y divide-border/60">
        {isLoading &&
          Array.from({ length: WIRE_ROWS }, (_, i) => (
            <li key={i} className="h-9 flex items-center px-3">
              <span className="h-3 w-full max-w-64 animate-pulse rounded-sm bg-muted" />
            </li>
          ))}
        {!isLoading && rows.length === 0 && (
          <li className="px-3 py-3 text-[13px] text-muted-foreground">No filings yet.</li>
        )}
        {rows.map((f) => (
          <li
            key={`${f.fund}-${f.ticker}-${f.filingDate}`}
            className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 px-3 h-9 text-[13px]"
          >
            <span className="text-xs text-muted-foreground tabular-nums">
              {f.filingDate.slice(5)}
            </span>
            <span className="truncate">
              <Link to={fundPath(f.fund)} className="fund-link">
                {f.fund}
              </Link>{" "}
              <Link to={stockPath(f.ticker)} className="ticker-link">
                {f.ticker}
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
  const tickers = new Set(stocks.map((s) => s.ticker)).size;

  usePageMeta({
    title: "Hedge Fund Tracker — SEC Filing Tracker & Hedge Fund Analytics",
    description:
      "SEC filings from a roster of hedge funds selected by measured performance, turned into portfolios, deltas and consensus you can read in seconds.",
    canonical: canonicalUrl(ROUTES.home),
  });

  return (
    // One screen on desktop: the root owns the height main gives it and the
    // hero row takes what is left, so nothing pushes the footer out of view.
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 lg:h-full lg:min-h-0">
      <section className="grid gap-4 lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:gap-6">
        {/* The claim, with the mark carrying it. */}
        <div className="flex min-w-0 min-h-0 flex-col gap-4">
          {/* The mark is the column's optical weight, not an app icon: no
              plate, no border, sized against the headline block beside it. */}
          <div className="flex items-center gap-4 sm:gap-6">
            <img
              src={`${BASE_PATH}/logo.png`}
              alt="Hedge Fund Tracker"
              className="h-24 w-24 shrink-0 object-contain sm:h-52 sm:w-52"
            />
            <div className="min-w-0 space-y-3">
              <h1 className="max-w-[18ch] text-[clamp(1.5rem,3.4vw,2.25rem)] font-semibold leading-[1.15] tracking-[-0.01em] text-foreground">
                No Buffett. No Burry. Only the best track records.
              </h1>
              <p className="max-w-[62ch] text-[13px] leading-5 text-muted-foreground">
                SEC filings from a roster of funds selected by measured performance, turned into
                portfolios, deltas and consensus you can read in seconds.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              to={ROUTES.latest}
              className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-[13px] font-medium text-primary-foreground transition-colors duration-[120ms] hover:brightness-110"
            >
              Open the board
            </Link>
            <a
              href="https://github.com/dokson/hedge-fund-tracker"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-9 items-center justify-center gap-2 rounded-md px-3 text-[13px] font-medium text-muted-foreground transition-colors duration-[120ms] hover:bg-muted hover:text-foreground"
            >
              <GitHubMark className="h-4 w-4" /> Source
            </a>
          </div>

          <div className="status-line flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>
              <span className="k">Funds tracked</span> {funds.length || "…"}
            </span>
            <span aria-hidden="true">·</span>
            <span>
              <span className="k">Tickers</span> {tickers || "…"}
            </span>
            <span aria-hidden="true">·</span>
            <span>
              <span className="k">Source</span> SEC EDGAR
            </span>
          </div>

          {/* What it is: three lines on hairlines, not three cards. */}
          <ul className="border-t border-border">
            {FEATURES.map((f) => (
              <li key={f.title} className="border-b border-border py-2">
                <h2 className="text-[13px] font-semibold text-foreground">{f.title}</h2>
                <p className="text-[13px] leading-5 text-muted-foreground">{f.body}</p>
              </li>
            ))}
          </ul>

          <p className="text-[13px] leading-5 text-muted-foreground">
            Most 13F trackers show holdings that are 45 or more days stale. The faster filings are
            stacked on top of the quarterly snapshot, so the picture reflects what funds are doing
            now.{" "}
            <Link to={learnItem("how-funds-are-selected")} className="ticker-link">
              How funds are selected
            </Link>
          </p>
        </div>

        {/* The proof: live filings, and the lag that makes them worth reading. */}
        <div className="flex min-w-0 min-h-0 flex-col gap-4 lg:gap-6">
          <Wire />
          <div className="frame">
            <div className="frame-title">
              <PanelTitle level={2}>A consensus that is current</PanelTitle>
              <span className="text-xs text-muted-foreground">Time to public, same scale</span>
            </div>
            <div className="space-y-2 p-3">
              {FRESHNESS.map((f) => (
                <div
                  key={f.tag}
                  className="grid grid-cols-[7ch_minmax(0,1fr)_11ch] items-center gap-3 text-[13px]"
                >
                  <span className="font-medium text-foreground">{f.tag}</span>
                  <div className="h-2 rounded-sm bg-muted" aria-hidden="true">
                    <div
                      className={cn("h-full rounded-sm", f.bar)}
                      style={{ width: `${(f.days / MAX_LAG) * 100}%` }}
                    />
                  </div>
                  <span className="text-right text-muted-foreground tabular-nums">{f.lag}</span>
                  <span className="sr-only">{f.label}</span>
                </div>
              ))}
              <p className="border-t border-border pt-2 text-xs leading-5 text-muted-foreground">
                Each bar is the delay until that filing becomes public, on a calendar-day scale.
                Form 4 and Schedule 13D land on top of the 45-day-old 13F. A Schedule 13G can be
                just as fast, but a large institution's is due 45 days after quarter end, the same
                lag as a 13F.
              </p>
            </div>
          </div>
        </div>
      </section>

      <footer className="status-note flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-3">
        <span>
          Built by{" "}
          <a
            href="https://www.coalesce.coach/en"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="COalesCE website"
            className="text-foreground underline underline-offset-2"
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
