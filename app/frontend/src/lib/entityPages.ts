/**
 * Build-time summaries and static HTML for the per-stock and per-fund pages
 * the gh-pages build pre-renders. Pure and React-free so the Vite config can
 * run it in Node over the quarter CSVs; titles and descriptions mirror the live
 * StockAnalysis / FundPortfolio pages so the hydrated SPA agrees with the HTML.
 */
import { pageTitle, SITE_NAME } from "./pageMeta.ts";
import type { PublicPage } from "./pageMeta.ts";
import { fundPath, ROUTES, stockPath } from "./routes.ts";
import { canonicalUrl, escapeAttr, escapeHtml } from "./seo.ts";

/** A stock page needs this many distinct holders to carry more than a stub. */
export const MIN_HOLDERS_FOR_PAGE = 3;

/** Tickers a static host serves as-is; a dot would be read as a file extension. */
const URL_SAFE_TICKER = /^[A-Z0-9-]+$/;

export interface QuarterRow {
  fund: string;
  ticker: string;
  company: string;
  value: number;
  portfolioPct: number;
  /** `NEW`, `CLOSE`, `NO CHANGE` or a signed percentage such as `+12.5%`. */
  delta: string;
}

export interface Holding {
  fund: string;
  ticker: string;
  company: string;
  value: number;
  portfolioPct: number;
  delta: string;
}

export interface StockSummary {
  ticker: string;
  company: string;
  holders: Holding[];
  buyers: number;
  sellers: number;
  totalValue: number;
}

export interface FundMeta {
  fund: string;
  manager: string;
  denomination: string;
}

export interface FundSummary extends FundMeta {
  holdings: Holding[];
  positions: number;
  totalValue: number;
  opened: number;
  closed: number;
}

const SUFFIX: Record<string, number> = { K: 1e3, M: 1e6, B: 1e9, T: 1e12 };

/** Reads a quarter file's Value cell (`568.43M`, `950K`, `1234`); 0 when unreadable. */
export function parseReportedValue(raw: string): number {
  const match = /^\s*(-?[\d.]+)\s*([KMBT]?)\s*$/i.exec(raw);
  if (!match) return 0;
  const amount = Number(match[1]);
  return Number.isFinite(amount) ? amount * (SUFFIX[match[2].toUpperCase()] ?? 1) : 0;
}

function isBuy(delta: string): boolean {
  return delta === "NEW" || /^\+\d*\.?\d*[1-9]/.test(delta);
}

function isSell(delta: string): boolean {
  return delta === "CLOSE" || delta.startsWith("-");
}

/** Merges a fund's several lines on one ticker (e.g. stock plus a convertible). */
function mergeHolding(into: Holding | undefined, line: QuarterRow): Holding {
  if (!into) return { ...line };
  return {
    ...into,
    value: into.value + line.value,
    portfolioPct: into.portfolioPct + line.portfolioPct,
    delta: into.delta === "NO CHANGE" ? line.delta : into.delta,
  };
}

/** One summary per ticker: open holders by value, plus buyer/seller counts. */
export function buildStockSummaries(
  rows: readonly QuarterRow[],
  companyByTicker: Readonly<Record<string, string>>,
): Map<string, StockSummary> {
  const byTicker = new Map<string, Map<string, Holding>>();
  const closedBy = new Map<string, Set<string>>();
  for (const line of rows) {
    if (!line.ticker) continue;
    if (line.delta === "CLOSE") {
      closedBy.set(line.ticker, (closedBy.get(line.ticker) ?? new Set()).add(line.fund));
      continue;
    }
    const funds = byTicker.get(line.ticker) ?? new Map<string, Holding>();
    funds.set(line.fund, mergeHolding(funds.get(line.fund), line));
    byTicker.set(line.ticker, funds);
  }

  const summaries = new Map<string, StockSummary>();
  for (const [ticker, funds] of byTicker) {
    const holders = [...funds.values()].sort((a, b) => b.value - a.value);
    summaries.set(ticker, {
      ticker,
      company: companyByTicker[ticker] || holders[0]?.company || ticker,
      holders,
      buyers: holders.filter((h) => isBuy(h.delta)).length,
      sellers: holders.filter((h) => isSell(h.delta)).length + (closedBy.get(ticker)?.size ?? 0),
      totalValue: holders.reduce((sum, h) => sum + h.value, 0),
    });
  }
  return summaries;
}

/** One summary per fund in `funds` that filed this quarter. */
export function buildFundSummaries(
  rows: readonly QuarterRow[],
  funds: readonly FundMeta[],
): FundSummary[] {
  return funds.flatMap((meta) => {
    const lines = rows.filter((r) => r.fund === meta.fund);
    if (lines.length === 0) return [];
    const merged = new Map<string, Holding>();
    for (const line of lines) {
      if (line.delta === "CLOSE" || !line.ticker) continue;
      merged.set(line.ticker, mergeHolding(merged.get(line.ticker), line));
    }
    const holdings = [...merged.values()].sort((a, b) => b.value - a.value);
    return [
      {
        ...meta,
        holdings,
        positions: holdings.length,
        totalValue: holdings.reduce((sum, h) => sum + h.value, 0),
        opened: holdings.filter((h) => h.delta === "NEW").length,
        closed: lines.filter((l) => l.delta === "CLOSE").length,
      },
    ];
  });
}

/** `$2.50B`, `$950.00K`. */
export function formatUsd(value: number): string {
  for (const [suffix, size] of [
    ["T", 1e12],
    ["B", 1e9],
    ["M", 1e6],
    ["K", 1e3],
  ] as const) {
    if (Math.abs(value) >= size) return `$${(value / size).toFixed(2)}${suffix}`;
  }
  return `$${value.toFixed(0)}`;
}

/** `2026Q2` → `2026 Q2`. */
function quarterLabel(quarter: string): string {
  return quarter.replace("Q", " Q");
}

function fundLabel(meta: FundMeta): string {
  return meta.denomination || meta.fund;
}

/** Page metadata for a stock, or null when it does not earn a static page. */
export function stockEntityPage(summary: StockSummary): PublicPage | null {
  if (summary.holders.length < MIN_HOLDERS_FOR_PAGE) return null;
  if (!URL_SAFE_TICKER.test(summary.ticker)) return null;
  const { ticker, company } = summary;
  return {
    path: stockPath(ticker),
    title: pageTitle(company === ticker ? ticker : `${ticker} · ${company}`),
    description: `Which hedge funds hold ${company} (${ticker}), how much, and how those positions moved quarter over quarter, from SEC 13F filings.`,
    heading: `${ticker} — ${company}`,
  };
}

export function fundEntityPage(summary: FundSummary): PublicPage {
  const label = fundLabel(summary);
  return {
    path: fundPath(summary.fund),
    title: pageTitle(label),
    description: `${label}'s reported holdings from its latest SEC 13F filing: positions, portfolio weights and quarter-over-quarter changes.`,
    heading: label,
  };
}

const DISCLAIMER =
  "<p>Source: SEC EDGAR 13F filings, reported as of quarter end and filed up to 45 days later. Not investment advice.</p>";

function link(path: string, label: string): string {
  return `<a href="${escapeAttr(canonicalUrl(path))}">${escapeHtml(label)}</a>`;
}

function table(headers: string[], rows: string[][]): string {
  const head = headers.map((h) => `<th>${h}</th>`).join("");
  const body = rows.map((cells) => `<tr>${cells.map((c) => `<td>${c}</td>`).join("")}</tr>`);
  return `<table><thead><tr>${head}</tr></thead><tbody>${body.join("")}</tbody></table>`;
}

/** Static body of a stock page: a quotable fact sentence and the holders table. */
export function renderStockBody(
  summary: StockSummary,
  ctx: { quarter: string; trackedFunds: number },
): string {
  const { ticker, company, holders, buyers, sellers, totalValue } = summary;
  const fact =
    `In ${quarterLabel(ctx.quarter)}, ${holders.length} of the ${ctx.trackedFunds} tracked hedge funds ` +
    `reported a position in ${escapeHtml(company)} (${escapeHtml(ticker)}), worth ${formatUsd(totalValue)} combined. ` +
    `Over the quarter ${buyers} opened or added, ${sellers} trimmed or exited.`;
  const rows = holders.map((h) => [
    link(fundPath(h.fund), h.fund),
    formatUsd(h.value),
    `${h.portfolioPct.toFixed(2)}%`,
    escapeHtml(h.delta),
  ]);
  return [
    "<main>",
    `<h1>${escapeHtml(ticker)} — ${escapeHtml(company)}</h1>`,
    `<p>${fact}</p>`,
    `<h2>Hedge fund holders, ${quarterLabel(ctx.quarter)}</h2>`,
    table(["Fund", "Value", "Portfolio %", "Change"], rows),
    `<p>${link(ROUTES.stocks, "All stocks")} · ${link(ROUTES.quarterly, "Quarterly Trends")} · ${link(ROUTES.home, SITE_NAME)}</p>`,
    DISCLAIMER,
    "</main>",
  ].join("");
}

/** Static body of a fund page: summary sentence and the top holdings. */
/** One quarter of a fund's holding-based return; null index values were unpriced. */
export interface TrackPoint {
  quarter: string;
  fundReturn: number;
  indexReturn: number | null;
  fundCum: number;
  indexCum: number | null;
}

const signedPct = (value: number | null) =>
  value === null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;

/** Track-record section of a fund page; empty when nothing was measured. */
function renderTrackRecord(track: readonly TrackPoint[]): string {
  const first = track[0];
  const last = track.at(-1);
  if (!first || !last) return "";
  const versus =
    last.indexCum === null ? "" : ` against ${signedPct(last.indexCum)} for the S&amp;P 500`;
  const summary =
    `Since ${quarterLabel(first.quarter)} the disclosed positions returned an estimated ${signedPct(last.fundCum)}${versus}. ` +
    "Estimated return of the fund's disclosed US long positions at the start of each quarter (top 100 by value), price-only. " +
    "Not the fund's actual return: excludes trading within the quarter, fees, shorts, derivatives and cash. " +
    "Benchmark: S&amp;P 500 price return over the same quarter-end windows.";
  const rows = track.map((p) => [
    quarterLabel(p.quarter),
    signedPct(p.fundReturn),
    signedPct(p.indexReturn),
  ]);
  return [
    "<h2>Estimated return</h2>",
    `<p>${summary}</p>`,
    table(["Quarter", "Fund", "S&amp;P 500"], rows),
  ].join("");
}

export function renderFundBody(
  summary: FundSummary,
  ctx: {
    quarter: string;
    stockPages: ReadonlySet<string>;
    track?: readonly TrackPoint[];
    limit?: number;
  },
): string {
  const label = fundLabel(summary);
  const manager = summary.manager ? `, managed by ${escapeHtml(summary.manager)}` : "";
  const fact =
    `${escapeHtml(label)}${manager}, reported ${summary.positions} positions worth ${formatUsd(summary.totalValue)} ` +
    `in its ${quarterLabel(ctx.quarter)} 13F filing: ${summary.opened} new and ${summary.closed} closed.`;
  const rows = summary.holdings
    .slice(0, ctx.limit ?? 50)
    .map((h) => [
      ctx.stockPages.has(h.ticker) ? link(stockPath(h.ticker), h.ticker) : escapeHtml(h.ticker),
      escapeHtml(h.company),
      formatUsd(h.value),
      `${h.portfolioPct.toFixed(2)}%`,
      escapeHtml(h.delta),
    ]);
  return [
    "<main>",
    `<h1>${escapeHtml(label)}</h1>`,
    `<p>${fact}</p>`,
    renderTrackRecord(ctx.track ?? []),
    `<h2>Top holdings, ${quarterLabel(ctx.quarter)}</h2>`,
    table(["Ticker", "Company", "Value", "Portfolio %", "Change"], rows),
    `<p>${link(ROUTES.funds, "All funds")} · ${link(ROUTES.home, SITE_NAME)}</p>`,
    DISCLAIMER,
    "</main>",
  ].join("");
}
