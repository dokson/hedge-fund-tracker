/**
 * Content of the /about page: who builds the tracker, where the data comes
 * from, how to read it and what it cannot tell you. Plain data, like
 * faqContent.ts, so the React page and the gh-pages static pre-render share it.
 * Methodology is not repeated here: it links to the FAQ answers that own it.
 */
import { learnItem, ROUTES } from "./routes.ts";
import { canonicalUrl, escapeAttr, escapeHtml } from "./seo.ts";

/** Plain text, or a link: `href` is an in-app path or an absolute URL. */
export type Segment = string | { text: string; href: string };

export interface AboutSection {
  id: string;
  title: string;
  /** One entry per paragraph, each a run of segments. */
  paragraphs: Segment[][];
}

/** Last content review (ISO 8601); the sitemap lastmod. Bump when the text changes. */
export const ABOUT_LAST_UPDATED = "2026-10-03";

export const ABOUT_HEADING = "About Hedge Fund Tracker";

export const ABOUT_INTRO =
  "Hedge Fund Tracker reads the SEC filings of a curated roster of hedge funds and turns them into portfolios, quarter-over-quarter changes and cross-fund consensus you can read in seconds.";

const REPO = "https://github.com/dokson/hedge-fund-tracker";

export const ABOUT_SECTIONS: AboutSection[] = [
  {
    id: "who",
    title: "Who builds it",
    paragraphs: [
      [
        "The tracker is built and maintained by ",
        { text: "COalesCE", href: "https://www.coalesce.coach/en" },
        ". Its code is public on ",
        { text: "GitHub", href: REPO },
        " as a source-available project; the documentation is published under CC BY 4.0.",
      ],
    ],
  },
  {
    id: "independence",
    title: "Independence",
    paragraphs: [
      [
        "Hedge Fund Tracker is independent: it has no commercial relationship with the funds it tracks, carries no advertising or sponsored placement, and no fund can pay to be included or left out. The roster follows the selection criteria alone.",
      ],
      [
        "The data spans most of the US stock market, so the authors may hold positions in securities shown on the site. Nothing here is a recommendation to buy or sell.",
      ],
    ],
  },
  {
    id: "data",
    title: "Where the data comes from",
    paragraphs: [
      [
        "Every holding comes from public filings on SEC EDGAR: quarterly 13F reports, 13D and 13G ownership filings, and Form 4 insider trades. New filings are collected automatically and published after review, so the site can trail EDGAR; the quarter it covers is shown at the top of every page. ",
        { text: "Where the data comes from", href: learnItem("where-data-comes-from") },
        " explains the sources in detail.",
      ],
      [
        "Filings arrive with a legal delay. A 13F is due within 45 days of quarter end; a 13D within 5 business days; a 13G within 5 business days for passive investors and 45 days after quarter end for qualified institutions; a Form 4 within 2 business days. The tracker layers the faster filings on top of the quarterly snapshot. See ",
        { text: "how current the data is", href: learnItem("how-current-is-data") },
        ".",
      ],
    ],
  },
  {
    id: "roster",
    title: "How the funds are chosen",
    paragraphs: [
      [
        "The roster is curated, not exhaustive. Funds are picked by a score that rewards cumulative returns while penalising volatility and drawdowns; underperformers are removed and strong performers added as the record evolves (",
        { text: "how the tracked funds are selected", href: learnItem("how-funds-are-selected") },
        ").",
      ],
      [
        "Specialist healthcare and biotech funds and very large, highly diversified managers are left out on purpose, because a consensus read loses meaning on portfolios that broad. Since every tracked fund is pre-selected on past performance, their results are not a ranking of hedge funds in general.",
      ],
    ],
  },
  {
    id: "reported-vs-computed",
    title: "What is reported and what is computed",
    paragraphs: [
      [
        "Positions, share counts, values and filing dates are what the funds reported to the SEC, and each fund's quarterly file is kept faithful to its filing. Everything built on top is computed here: quarter-over-quarter changes, consensus counts, Avg Portfolio %, the Smart Score, estimated fund returns and the strategy backtest. Share counts are restated across stock splits, so a split never reads as a purchase.",
      ],
      [
        "The Smart Score uses institutional filing signals only, with no sell-side analyst ratings.",
      ],
    ],
  },
  {
    id: "methodology",
    title: "How to read the numbers",
    paragraphs: [
      [
        "Consensus screens weight each stock by ",
        { text: "Avg Portfolio %", href: learnItem("what-is-avg-portfolio-pct") },
        ", and the ",
        { text: "strategy backtest", href: learnItem("how-strategy-performance-is-backtested") },
        " shows how those screens would have performed against the S&P 500.",
      ],
      [
        "A fund's estimated return is the price change of the US long positions it disclosed at the start of each quarter. It is not the fund's actual return: trading within the quarter, fees, shorts, derivatives and cash are invisible in the filings.",
      ],
    ],
  },
  {
    id: "limits",
    title: "What the filings cannot show",
    paragraphs: [
      [
        "Filings cover US long equity only and show a fund's book weeks after the fact. Read ",
        { text: "what this data cannot show", href: learnItem("what-data-cannot-show") },
        " before acting on any figure.",
      ],
    ],
  },
  {
    id: "contact",
    title: "Corrections and contact",
    paragraphs: [
      [
        "Spotted a wrong number, a mismatched ticker or a missing fund? ",
        { text: "Open an issue on GitHub", href: `${REPO}/issues` },
        ". Corrections are welcome.",
      ],
      [
        "Two known sources of error are worth checking first: 13D/G and Form 4 filings are matched to a fund by its exact legal name, so a name mismatch leaves a gap in the faster-filing view; and ticker and CUSIP mappings come from public sources and can be wrong, especially after a rename.",
      ],
    ],
  },
  {
    id: "privacy",
    title: "Privacy",
    paragraphs: [
      [
        "There are no accounts and no analytics or advertising scripts. Starred funds and stocks are saved only in your browser, and a cookie remembers whether the sidebar is collapsed. Company and fund logos are loaded through Cloudinary, so your browser contacts that service to display them.",
      ],
    ],
  },
  {
    id: "licensing",
    title: "Using and citing the data",
    paragraphs: [
      [
        "The datasets this site publishes are licensed ",
        { text: "CC BY-NC 4.0", href: `${REPO}/blob/master/LICENSE-DATA` },
        ": you may reuse them for non-commercial purposes, crediting Hedge Fund Tracker with a link to this site. Commercial use needs written permission. The underlying filings remain public records on SEC EDGAR.",
      ],
    ],
  },
  {
    id: "disclaimer",
    title: "Disclaimer",
    paragraphs: [
      [
        "Everything on this site is for information only and is not investment advice. Filings are disclosed with a delay and show only part of a fund's portfolio; every figure derived from them, including estimated returns and scores, is an approximation that may contain errors. Do your own research before making any investment decision.",
      ],
    ],
  },
];

/** Absolute URL for a segment link (in-app paths resolve against the site). */
export function segmentHref(href: string): string {
  if (!href.startsWith("/")) return href;
  const [path, hash] = href.split("#", 2);
  return hash === undefined ? canonicalUrl(path) : `${canonicalUrl(path)}#${hash}`;
}

/** Static HTML body of the about page for crawlers that don't run JavaScript. */
export function renderAboutBody(): string {
  const paragraph = (segments: Segment[]) =>
    `<p>${segments
      .map((seg) =>
        typeof seg === "string"
          ? escapeHtml(seg)
          : `<a href="${escapeAttr(segmentHref(seg.href))}">${escapeHtml(seg.text)}</a>`,
      )
      .join("")}</p>`;
  const sections = ABOUT_SECTIONS.map(
    (s) =>
      `<section id="${s.id}"><h2>${escapeHtml(s.title)}</h2>${s.paragraphs.map(paragraph).join("")}</section>`,
  ).join("");
  return [
    "<main>",
    `<h1>${escapeHtml(ABOUT_HEADING)}</h1>`,
    `<p>${escapeHtml(ABOUT_INTRO)}</p>`,
    sections,
    `<p><a href="${escapeAttr(canonicalUrl(ROUTES.home))}">Hedge Fund Tracker</a></p>`,
    "</main>",
  ].join("");
}
