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
export const FAQ_LAST_UPDATED = "2026-09-03";

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
          "Both are ownership disclosures triggered when an investor comes to beneficially own more than 5% of a company's registered voting shares, but they signal different intent. A Schedule 13D is the \"activist\" filing, used when the investor may seek to influence or control the company; it carries far more detail and, since the SEC's 2023 amendments to Regulation 13D-G, must be filed within five business days of the acquisition, with amendments due within two business days of a material change.",
          'A Schedule 13G is the short-form, "passive" version, for investors holding the stake without intent to influence control. Its deadline depends on who is filing: a large regulated institution — the SEC calls it a Qualified Institutional Investor — files 45 days after the end of the calendar quarter in which it passed 5%, while a passive investor files within five business days of the acquisition. Both file faster once ownership passes 10%: five business days after that month\'s end for the institution, two business days for the passive investor.',
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
        id: "does-13f-show-shorts",
        question: "Does a 13F show short positions?",
        answer: [
          "No. Short stock positions are not reportable on Form 13F, and a manager may not net a short against a long in the same security — only the long position is reported. A fund that is net short a name can therefore still appear in the data as owning it.",
          "The one nuance is that put options a manager holds are reportable when the underlying is on the SEC's list, and they appear flagged as puts: a bearish position sitting inside an otherwise long-looking report.",
        ],
      },
      {
        id: "what-is-13f-nt",
        question: "What is a 13F-NT, and what does an amendment mean?",
        answer: [
          'A 13F-HR ("holdings report") is the filing that actually lists positions. A 13F-NT ("notice") says the manager reports no holdings on its own form because they are all reported on another manager\'s filing, commonly a parent or affiliate — so a 13F-NT is not a fund that sold everything.',
          "A filing ending in /A, such as 13F-HR/A, is an amendment that restates or adds to an earlier report. This tracker matches filings by the quarter they refer to and takes the most recently published version, so an amendment replaces the original.",
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
          "Most 13F trackers show only quarterly data, which can be more than 45 days stale and miss large recent trades. This tracker layers the faster filings on top: Schedule 13D/G ownership disclosures and Form 4 insider transactions, which in the fastest cases arrive within a few business days of the event.",
          "The trade-off is that the three filings are not the same kind of measurement. A 13F is a full snapshot of one manager's reportable holdings on the quarter's last day. A 13D/G reports a percentage stake in a single company as of the date a threshold was crossed, and only above 5%. A Form 4 reports one transaction by one insider, which may be a share grant rather than a decision to buy. Combining them gives a more current picture, but the dates, the units and the coverage differ — so read the merged view as a directional signal, not as a reconstructed portfolio.",
        ],
      },
      {
        id: "what-is-promise-score",
        question: "What is the Promise Score?",
        answer: [
          "The Promise Score is a ranking produced by a language model from the institutional filing data on this site: how many tracked funds hold a stock, how large those positions are, and how they changed over recent quarters. It runs in two steps — the model first proposes how much weight to give each of those inputs, then scores every stock using those weights.",
          "It is a way of sorting a long list into a shorter one. It is not a forecast and not investment advice: nothing in it looks at fundamentals, valuation or price, and the weights are the model's judgment rather than a tested result. Do your own research before acting on it.",
        ],
      },
      {
        id: "how-funds-are-selected",
        question: "How are the tracked funds selected?",
        answer: [
          "The fund list is curated, not exhaustive. A custom method favors strong cumulative returns while penalizing volatility, in the spirit of the Sharpe ratio, and penalizing drawdowns, in the spirit of the Sterling ratio. The drawdown penalty is deliberately softened for funds that recover well from a bad stretch.",
          "Highly specialised funds (for example healthcare/biotech) and the largest, most diversified mega-funds are intentionally excluded, because analysis quality tends to drop when tracking very large or narrow portfolios.",
        ],
      },
      {
        id: "what-is-avg-portfolio-pct",
        question: 'What does "Avg Portfolio %" mean?',
        answer: [
          "Avg Portfolio % is the average weight a stock represents across the tracked funds that hold it. A higher value means the funds that own the position are, on average, allocating more of their portfolio to it.",
          "It measures conviction, not popularity: it is an average across the funds that hold the stock, so a position held by one fund at 12% of its portfolio scores higher than one held by twenty funds at 6% each. Read it next to the number of holding funds, which is where breadth actually shows up.",
        ],
      },
      {
        id: "how-strategy-performance-is-backtested",
        question: "How is the strategy performance backtested?",
        answer: [
          "Each strategy on the Strategy Performance page is entered on the date its 13F becomes public — 45 days after quarter-end — and held until the next quarter's filing, then rebalanced. That filing date is the first day the holdings are actually known.",
          "Measuring a quarter's holdings during the quarter they refer to (for example, January to March for the first quarter) would be look-ahead bias: you cannot trade on positions that are not disclosed until 45 days later. Entering at the filing date removes that one bias, and it follows the convention used in published research on 13F holdings.",
          "Returns are conviction-weighted by each stock's average portfolio weight across the holding funds and compared to the S&P 500. Only fully-elapsed quarters are shown.",
          "Read the result as a description, not as evidence of an edge. The sample covers a small number of quarters in a single market regime, with no significant down quarter yet, so most of the gap versus the index is exposure to a rising market — a screen built on funds reducing their positions beat the index over the same window, for that reason. The figures include no trading costs or slippage, and the tracked fund list is curated and revised over time, which flatters any backtest run on it. Past results here say nothing about future returns.",
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
          "It depends on the filing type. A 13F can be 45 days old or more. A Schedule 13D is due within five business days of the trigger. A Schedule 13G is faster only in some cases: a passive investor files within five business days, but a large regulated institution files 45 days after the end of the quarter — the same lag as a 13F. A Form 4 is due within two business days. Merging the three reduces, but cannot eliminate, the lag built into disclosure-based tracking.",
        ],
      },
    ],
  },
];
