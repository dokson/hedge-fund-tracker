/**
 * Single source of truth (TypeScript side) for the seven cross-fund consensus
 * strategies surfaced in QuarterlyTrends and backtested on the /performance page.
 *
 * The canonical fields (id, label, metric, ascending, minHolders,
 * excludeInfiniteDelta, capped, topN) are pinned to tests/fixtures/strategies.json
 * — generated from the Python `app/backtest/strategies.py` — by the guard test in
 * `__tests__/strategies.test.ts`, so the UI and the backtest can't diverge.
 * (`description`/`note` are UI-only and intentionally not part of that fixture.)
 *
 * `tab` is the QuarterlyTrends tab id; `sortKey` is the AnalysisTable sort field
 * (camelCase) the canonical snake_case `metric` maps to.
 */

import {
  Banknote,
  Gauge,
  Handshake,
  PieChart,
  TrendingDown,
  TrendingUp,
  UserPlus,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface StrategyDef {
  /** Canonical id, identical to the Python strategy id. */
  id: string;
  /** QuarterlyTrends tab value. */
  tab: string;
  label: string;
  /** Lucide icon (shared by the QuarterlyTrends tab and the Performance card). */
  icon: LucideIcon;
  /** AnalysisTable sort field (camelCase). */
  sortKey: string;
  /** Canonical ranking metric (lower_snake of the analysis column). */
  metric: string;
  ascending: boolean;
  minHolders: boolean;
  /** Min-holders threshold = ceil(funds / minHoldersDivisor); defaults to 10. */
  minHoldersDivisor?: number;
  excludeInfiniteDelta: boolean;
  /** Whether the top-N cap applies (Avg Portfolio keeps every passing name). */
  capped: boolean;
  topN: number | null;
  /** One-line plain-language description (shared by the QuarterlyTrends + Performance tooltips). */
  description: string;
  /** Optional extra caveat shown only where performance is interpreted. */
  note?: string;
  /** Restrict the screen to this delta sign ("positive"/"negative"); undefined = no constraint. */
  deltaSign?: "positive" | "negative";
}

const TOP_N = 30;

export const STRATEGY_DEFS: StrategyDef[] = [
  {
    id: "smart_score",
    tab: "smartscore",
    label: "Smart Score",
    icon: Gauge,
    sortKey: "smartScore",
    metric: "smart_score",
    ascending: false,
    minHolders: false,
    excludeInfiniteDelta: false,
    capped: true,
    topN: TOP_N,
    description:
      "Stocks ranked by the composite 1-10 smart score: breadth, momentum and conviction percentiles from institutional signals only, computed on the fly for the selected quarter.",
    note: "The exact same formula is backtested on the Performance page — no analyst inputs, no tuning.",
  },
  {
    id: "avg_portfolio",
    tab: "avgportfolio",
    label: "Avg Portfolio",
    icon: PieChart,
    sortKey: "avgPortfolioPct",
    metric: "avg_portfolio_pct",
    ascending: false,
    minHolders: true,
    excludeInfiniteDelta: false,
    capped: false,
    topN: null,
    description: "Stocks ranked by average portfolio weight across all tracked funds.",
  },
  {
    id: "consensus",
    tab: "consensus",
    label: "Consensus Buys",
    icon: Handshake,
    sortKey: "netBuyers",
    metric: "net_buyers",
    ascending: false,
    minHolders: false,
    excludeInfiniteDelta: false,
    capped: true,
    topN: TOP_N,
    description: "Stocks with the most net buyers (buyers minus sellers) this quarter.",
  },
  {
    id: "new_consensus",
    tab: "new",
    label: "New Consensus",
    icon: UserPlus,
    sortKey: "newHolderCount",
    metric: "new_holder_count",
    ascending: false,
    minHolders: false,
    excludeInfiniteDelta: false,
    capped: true,
    topN: TOP_N,
    description: "Stocks attracting the most brand-new holders this quarter.",
  },
  {
    id: "big_bets",
    tab: "bigbets",
    label: "Big Bets",
    icon: Banknote,
    sortKey: "maxPortfolioPct",
    metric: "max_portfolio_pct",
    ascending: false,
    minHolders: false,
    excludeInfiniteDelta: false,
    capped: true,
    topN: TOP_N,
    description: "Stocks with the highest portfolio concentration in a single fund.",
  },
  {
    id: "increasing",
    tab: "increasing",
    label: "Increasing",
    icon: TrendingUp,
    sortKey: "delta",
    metric: "delta",
    ascending: false,
    minHolders: true,
    excludeInfiniteDelta: true,
    capped: true,
    topN: TOP_N,
    description: "Stocks with the largest percentage increase in aggregate shares held.",
    deltaSign: "positive",
  },
  {
    id: "decreasing",
    tab: "decreasing",
    label: "Decreasing",
    icon: TrendingDown,
    sortKey: "totalDeltaValue",
    metric: "total_delta_value",
    ascending: true,
    minHolders: false,
    excludeInfiniteDelta: false,
    capped: true,
    topN: TOP_N,
    description: "Stocks with the largest dollar decrease in aggregate institutional value.",
    deltaSign: "negative",
    note: "In theory this isn't a strategy to follow — these are positions funds are trimming. It still beats the market here because the tracked funds hold mostly outperforming stocks, so even the names they reduce tend to outperform.",
  },
];

/** Strategy def keyed by QuarterlyTrends tab value. */
export const STRATEGY_BY_TAB: Record<string, StrategyDef> = Object.fromEntries(
  STRATEGY_DEFS.map((d) => [d.tab, d]),
);

/** Strategy def keyed by canonical id. */
export const STRATEGY_BY_ID: Record<string, StrategyDef> = Object.fromEntries(
  STRATEGY_DEFS.map((d) => [d.id, d]),
);

/** Display order for the Strategy Performance page (cards, legend, drill-down pills).
 * `smart_score` leads — it's the house strategy. */
const PERFORMANCE_ORDER = [
  "smart_score",
  "consensus",
  "new_consensus",
  "big_bets",
  "avg_portfolio",
  "increasing",
  "decreasing",
];

/** Strategy defs in the Performance page's display order. */
export const STRATEGY_DEFS_PERF_ORDER: StrategyDef[] = PERFORMANCE_ORDER.map(
  (id) => STRATEGY_BY_ID[id],
).filter(Boolean);

/** Index of a strategy id in the Performance display order (unknown ids sort last). */
export const perfOrderIndex = (id: string): number => {
  const i = PERFORMANCE_ORDER.indexOf(id);
  return i === -1 ? PERFORMANCE_ORDER.length : i;
};
