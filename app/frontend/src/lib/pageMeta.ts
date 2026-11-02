/**
 * Title, description and heading of every public, non-parametrised route. The
 * live pages and the gh-pages static pre-renderer both read this table, so the
 * crawler-facing HTML and the hydrated SPA can never drift apart. Kept free of
 * React so the Vite config can import it in Node.
 */
import { FAQ_META } from "./faqContent.ts";
import { ROUTES } from "./routes.ts";

/** Brand suffix every route title ends with (SC 2.4.2 wants distinct titles). */
export const SITE_NAME = "Hedge Fund Tracker";

/** `"Latest Filings — Hedge Fund Tracker"`. */
export function pageTitle(page: string): string {
  return `${page} — ${SITE_NAME}`;
}

export interface PublicPage {
  path: string;
  title: string;
  description: string;
  /** Visible H1 and the label used when other pages link here. */
  heading: string;
}

export const HOME_PAGE: PublicPage = {
  path: ROUTES.home,
  title: "Hedge Fund Tracker — SEC Filing Tracker & Hedge Fund Analytics",
  description:
    "Research stocks through SEC filings from funds selected by measured performance. Compare quarterly conviction and examine recent ownership disclosures.",
  heading: "No Buffett. No Burry. Selected by measured performance.",
};

export const LATEST_PAGE: PublicPage = {
  path: ROUTES.latest,
  title: pageTitle("Latest Filings"),
  description:
    "Latest saved 13D/G and Form 4 disclosures by publication date, with position dates, share changes against each fund's latest 13F and estimated values.",
  heading: "Latest Filings",
};

export const QUARTERLY_PAGE: PublicPage = {
  path: ROUTES.quarterly,
  title: pageTitle("Quarterly Trends"),
  description:
    "Consensus screens built from the quarter's 13F holdings: most held, highest conviction, biggest increases and exits across every tracked hedge fund.",
  heading: "Quarterly Trends",
};

export const PERFORMANCE_PAGE: PublicPage = {
  path: ROUTES.strategyPerformance,
  title: pageTitle("Strategy Performance"),
  description:
    "Backtested returns for every consensus screen, rebalanced each quarter and held to the next, measured against the S&P 500.",
  heading: "Strategy Performance",
};

export const RANKING_PAGE: PublicPage = {
  path: ROUTES.fundRanking,
  title: pageTitle("Fund Ranking"),
  description:
    "Rank tracked funds by estimated 13F-holdings returns, with S&P 500 comparisons on each fund's observed quarters, coverage limits and consistency.",
  heading: "Fund Ranking",
};

export const FUNDS_PAGE: PublicPage = {
  path: ROUTES.funds,
  title: pageTitle("Fund Portfolios"),
  description:
    "Every tracked hedge fund's portfolio: position count, total institutional value, quarter-over-quarter change and the manager behind it.",
  heading: "Fund Portfolios",
};

export const STOCKS_PAGE: PublicPage = {
  path: ROUTES.stocks,
  title: pageTitle("Stocks"),
  description:
    "Every stock held by the tracked hedge funds, browsable by name, sector or Smart Score, with institutional value and holder count.",
  heading: "Stocks",
};

export const LEARN_PAGE: PublicPage = {
  path: ROUTES.learn,
  title: FAQ_META.title,
  description: FAQ_META.description,
  heading: FAQ_META.heading,
};

export const ABOUT_PAGE: PublicPage = {
  path: ROUTES.about,
  title: "About Hedge Fund Tracker — Data Sources & Methodology",
  description:
    "Who builds Hedge Fund Tracker, where its SEC filing data comes from and how fresh it is, how to read the numbers, and what 13F filings cannot show.",
  heading: "About Hedge Fund Tracker",
};

/** Every route the static build pre-renders and lists in the sitemap. */
export const PUBLIC_PAGES: readonly PublicPage[] = [
  HOME_PAGE,
  LATEST_PAGE,
  QUARTERLY_PAGE,
  PERFORMANCE_PAGE,
  RANKING_PAGE,
  FUNDS_PAGE,
  STOCKS_PAGE,
  LEARN_PAGE,
  ABOUT_PAGE,
];
