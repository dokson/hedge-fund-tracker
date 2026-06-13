/**
 * Single source of truth for in-app route paths. Use these constants and
 * builders everywhere instead of hardcoding path strings, so a slug change
 * (e.g. "/latest") happens in one place.
 */
export const ROUTES = {
  home: "/",
  latest: "/latest",
  quarterly: "/quarterly",
  strategyPerformance: "/performance",
  learn: "/learn",
  funds: "/funds",
  stocks: "/stocks",
  /** Base segment for a single stock page; use `stockPath()` for a full link. */
  stock: "/stock",
  aiRanking: "/ai-ranking",
  aiDiligence: "/ai-diligence",
  fundsConfig: "/funds-config",
  aiSettings: "/ai-settings",
  database: "/database",
} as const;

/** Link to a single stock's analysis page. */
export const stockPath = (ticker: string) => `${ROUTES.stock}/${encodeURIComponent(ticker)}`;

/** Link to a single fund's portfolio page. */
export const fundPath = (fund: string) => `${ROUTES.funds}/${encodeURIComponent(fund)}`;

/** Stocks browser pre-filtered by an industry. */
export const stocksByIndustry = (industry: string) =>
  `${ROUTES.stocks}?industry=${encodeURIComponent(industry)}`;

/** AI Due Diligence pre-loaded with a ticker. */
export const aiDiligenceFor = (ticker: string) =>
  `${ROUTES.aiDiligence}?ticker=${encodeURIComponent(ticker)}`;

/** Strategy Performance pre-focused on a strategy (by canonical id). */
export const performanceFor = (strategyId: string) =>
  `${ROUTES.strategyPerformance}?strategy=${encodeURIComponent(strategyId)}`;
