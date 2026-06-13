/**
 * Single source of truth for the /learn FAQ page content.
 *
 * Authored as plain data (no JSX) so it can be consumed by both the React page
 * (src/pages/Learn.tsx) and the build-time static pre-renderer (the gh-pages
 * Vite plugin in vite.config.ts), which bakes every answer into static HTML so
 * AI/search crawlers read the full content without executing JavaScript.
 *
 * Answers front-load a plain-language definition in the opening sentence and
 * stay self-contained, which is what makes a passage citable by AI search.
 */

/** A single question/answer pair. `answer` is one entry per paragraph. */
export interface FaqItem {
  /** Stable slug used for the anchor id and accordion key. */
  id: string;
  question: string;
  answer: string[];
}

/** A titled group of FAQ items. */
export interface FaqSection {
  id: string;
  title: string;
  items: FaqItem[];
}

/** Page-level metadata used for the document title, meta description and H1. */
export const FAQ_META = {
  /** Browser/tab + <title>; kept within the 50-60 char SEO sweet spot. */
  title: "Hedge Fund & SEC Filing FAQ — 13F, 13D/G, Form 4",
  /** Meta description; kept within the 150-160 char SEO sweet spot. */
  description:
    "Plain-English answers about hedge fund SEC filings: what a 13F, 13D/G and Form 4 are, when they're due, and how this tracker turns them into stock insight.",
  /** Visible page heading (single H1). */
  heading: "Hedge Fund & SEC Filing FAQ",
  /** Short intro shown under the H1 and used as the lead paragraph. */
  intro:
    "Everything you need to understand institutional SEC filings and how this tracker reads them. Definitions are deliberately concise and jargon-free.",
} as const;

/**
 * Last content review date (ISO 8601). Surfaced as a visible "last updated"
 * line and as schema `dateModified` — content freshness is a ranking and
 * AI-citation signal, so bump this whenever the answers are revised.
 */
export const FAQ_LAST_UPDATED = "2026-06-13";

export const FAQ_SECTIONS: FaqSection[] = [
  {
    id: "sec-filings",
    title: "SEC filings explained",
    items: [
      {
        id: "what-is-a-13f",
        question: "What is a 13F filing?",
        answer: [
          "A 13F is a quarterly report that institutional investment managers must file with the U.S. Securities and Exchange Commission (SEC) when they manage at least $100 million in qualifying U.S. equity assets. It is filed within 45 days of each quarter's end.",
          "The report is a snapshot of the manager's long positions in U.S.-listed securities as of the last day of the quarter. It does not include short positions, cash, or most non-U.S. holdings, so it shows what a fund owned — not its full strategy.",
        ],
      },
      {
        id: "13d-vs-13g",
        question: "What is the difference between a 13D and a 13G?",
        answer: [
          'Both are ownership disclosures triggered when an investor crosses 5% of a company\'s voting shares, but they signal different intent. A Schedule 13D is the "activist" filing, used when the investor may seek to influence or control the company; it carries more detail and must be filed within 10 days.',
          'A Schedule 13G is the short-form, "passive" version, available to investors who hold the stake without intent to influence control. Because both are event-driven, they surface significant stakes far sooner than the next quarterly 13F would.',
        ],
      },
      {
        id: "what-is-form-4",
        question: "What is an SEC Form 4?",
        answer: [
          "A Form 4 is an insider-trading disclosure filed when a company's officers, directors, or holders of more than 10% of its stock buy or sell shares. It must be filed within two business days of the transaction.",
          "Because of that short window, Form 4 offers a near real-time view of how the people closest to a company — and its largest shareholders — are actually trading it.",
        ],
      },
      {
        id: "when-are-13f-due",
        question: "When are 13F filings due?",
        answer: [
          "13F reports are due within 45 days after the end of each calendar quarter — roughly mid-February, mid-May, mid-August, and mid-November. Many managers file close to the deadline.",
          "This is why pure 13F data is often 45 or more days old by the time it becomes public: it reflects positions as of the quarter's last day, not today.",
        ],
      },
      {
        id: "what-are-13f-securities",
        question: "Which securities appear in a 13F?",
        answer: [
          'Only "13F securities" — a list the SEC publishes — are reportable. In practice this covers exchange-traded U.S. stocks and ETFs, plus certain options and convertible instruments.',
          "Short positions, cash, currencies, commodities, and most non-U.S. or private holdings are not reportable, which is the main reason a 13F is an incomplete picture of any fund.",
        ],
      },
      {
        id: "where-data-comes-from",
        question: "Where does this data come from?",
        answer: [
          "All filings are retrieved directly from SEC EDGAR, the Commission's official public database of company and fund disclosures. The raw 13F, 13D/G, and Form 4 documents are parsed into structured holdings rather than re-typed from a third party.",
        ],
      },
    ],
  },
  {
    id: "how-it-works",
    title: "How this tracker works",
    items: [
      {
        id: "why-merge-non-quarterly",
        question: "Why merge non-quarterly filings into the quarterly view?",
        answer: [
          "Most 13F trackers show only quarterly data, which can be over 45 days stale and miss large recent trades. This tracker layers the faster filings on top: 13D/G disclosures (filed within ~10 days) and Form 4 insider trades (within ~2 business days).",
          "The result is a consensus view that reflects not just the static quarter-end snapshot but the significant moves made since — a more current picture of where institutions are actually positioned.",
        ],
      },
      {
        id: "what-is-promise-score",
        question: "What is the Promise Score?",
        answer: [
          "The Promise Score is an AI-generated rating that ranks stocks by their growth potential based on hedge fund activity. It is produced in two phases: first an AI model picks the metric weights best suited to the current market, then it scores each stock using those weights.",
          "It is a research aid for surfacing high-conviction ideas, not investment advice — always pair it with your own due diligence.",
        ],
      },
      {
        id: "how-funds-are-selected",
        question: "How are the tracked funds selected?",
        answer: [
          "The fund list is curated, not exhaustive. A custom methodology favours strong cumulative returns while penalising volatility (in the spirit of the Sharpe ratio) and drawdowns (in the spirit of the Sterling ratio, with a dampened penalty for funds that recover well).",
          "Highly specialised funds (for example healthcare/biotech) and the largest, most diversified mega-funds are intentionally excluded, because analysis quality tends to drop when tracking very large or narrow portfolios.",
        ],
      },
      {
        id: "what-is-avg-portfolio-pct",
        question: "What does “Avg Portfolio %” mean?",
        answer: [
          "Avg Portfolio % is the average weight a stock represents across the tracked funds that hold it. A higher value means the funds that own the position are, on average, allocating more of their portfolio to it.",
          "It captures conviction and breadth at once, which is why it is used to weight positions across the strategy screens.",
        ],
      },
      {
        id: "how-strategy-performance-is-backtested",
        question: "How is the strategy performance backtested?",
        answer: [
          "Each strategy on the Strategy Performance page is entered on the date its 13F becomes public — 45 days after quarter-end — and held until the next quarter's filing, then rebalanced. That filing date is the first day the holdings are actually known.",
          "Measuring a quarter's holdings during the quarter they refer to (for example, January to March for the first quarter) would be look-ahead bias: you cannot trade on positions that are not disclosed until 45 days later. Entering at the filing date is what makes the track record realistic and replicable, and it is the standard approach in academic 13F studies.",
          "Returns are conviction-weighted by each stock's average portfolio weight across the holding funds and compared to the S&P 500. Only fully-elapsed quarters are shown, so the figures are a historical track record, not a prediction.",
        ],
      },
    ],
  },
  {
    id: "limitations",
    title: "Limitations to keep in mind",
    items: [
      {
        id: "what-data-cannot-show",
        question: "What can this data not show?",
        answer: [
          "Public filings only reveal long U.S. equity positions. They do not show short positions, hedges, derivatives, cash, or non-U.S. holdings, so a fund's reported book can differ substantially from its true exposure.",
          "Treat the data as one input into a broader analysis rather than a complete view of any manager's strategy.",
        ],
      },
      {
        id: "how-current-is-data",
        question: "How current is the data?",
        answer: [
          "It depends on the filing type: 13F data can be 45+ days old, 13D/G is filed within about 10 days of the triggering event, and Form 4 within about 2 business days. Merging the three reduces — but cannot eliminate — the inherent lag in disclosure-based tracking.",
        ],
      },
    ],
  },
];
