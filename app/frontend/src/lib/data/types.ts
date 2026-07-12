/**
 * Shared row and domain types for the data layer.
 *
 * `Raw*` interfaces describe CSV rows exactly as parsed (all-string fields,
 * CSV header casing); the domain interfaces below them are the parsed,
 * camelCase shapes the rest of the app consumes.
 */

// ---------- Raw CSV row types ----------

export interface RawHedgeFund {
  CIK: string;
  Fund: string;
  Manager: string;
  Denomination: string;
  CIKs: string;
  URL: string;
}

export interface RawStock {
  CUSIP: string;
  Ticker: string;
  Company: string;
  Industry?: string;
}

export interface RawNonQuarterly {
  Fund: string;
  CUSIP: string;
  Ticker: string;
  Company: string;
  Shares: string;
  Value: string;
  Avg_Price: string;
  Date: string;
  Filing_Date: string;
}

export interface RawQuarterlyHolding {
  CUSIP: string;
  Ticker: string;
  Company: string;
  Shares: string;
  Delta_Shares: string;
  Value: string;
  Delta_Value: string;
  Delta: string;
  "Portfolio%": string;
}

export interface RawModel {
  ID: string;
  Description: string;
  Client: string;
}

export interface RawSectorHierarchy {
  Sector: string;
  Industry: string;
  Count: string;
}

export interface RawPerformanceRow {
  series_type: string;
  series_id: string;
  label: string;
  quarter_in: string;
  quarter_out: string;
  entry_date: string;
  exit_date: string;
  n_stocks: string;
  window_return: string;
  cum_return: string;
  excess_return: string;
  turnover: string;
}

// ---------- Parsed domain types ----------

export interface HedgeFund {
  cik: string;
  fund: string;
  manager: string;
  denomination: string;
  ciks: string;
  url: string;
}

export type ExcludedHedgeFund = HedgeFund;

export interface Stock {
  cusip: string;
  ticker: string;
  company: string;
  sector?: string;
  industry?: string;
}

export interface PerfWindow {
  quarterOut: string;
  windowReturn: number;
  cumReturn: number;
  /** Strategy return minus the anchor benchmark (S&P 500) this window; null for benchmark series. */
  excessReturn: number | null;
}

export interface PerfSeries {
  id: string;
  label: string;
  type: "strategy" | "benchmark";
  windows: PerfWindow[];
  /** Cumulative return over all windows (last window's cum_return). */
  cumReturn: number;
  /** Sample standard deviation of the per-window returns (quarterly σ). */
  volatility: number;
  /** Cumulative excess vs the S&P 500 in percentage points (strategies only). */
  excessPp: number | null;
  /** Windows whose return beat the S&P 500 (strategies only). */
  beats: number;
  total: number;
}

export interface PerformanceData {
  /** Ordered exit-quarter labels shared by every series (chart x-axis). */
  quarters: string[];
  series: PerfSeries[];
  /** Entry date of the first window (ISO) — when the track record actually starts. */
  startDate: string;
  /** Quarter the first window is entered from (e.g. "2025Q1"); the chart origin label. */
  startQuarter: string;
}

export interface NonQuarterlyFiling {
  fund: string;
  cusip: string;
  ticker: string;
  company: string;
  shares: number;
  value: string;
  avgPrice: string;
  date: string;
  filingDate: string;
}

export interface QuarterlyHolding {
  cusip: string;
  ticker: string;
  company: string;
  shares: number;
  deltaShares: number;
  value: string;
  deltaValue: string;
  delta: string;
  portfolioPct: number;
}

export interface AIModel {
  id: string;
  description: string;
  client: string;
}

export interface SectorHierarchyEntry {
  sector: string;
  industry: string;
  count: number;
}

// ---------- Analysis types ----------

/** Fund-level holding for a single ticker within a quarter (after CUSIP aggregation) */
export interface FundTickerHolding {
  fund: string;
  ticker: string;
  company: string;
  shares: number;
  deltaShares: number;
  value: number;
  deltaValue: number;
  portfolioPct: number;
  portfolioPctRank: number;
  sharesDeltaPct: number;
  fundConcentrationRatio: number;
  delta: string;
  isBuyer: boolean;
  isSeller: boolean;
  isHolder: boolean;
  isNew: boolean;
  isClosed: boolean;
  isHighConviction: boolean;
}

/** Stock-level aggregated analysis for a quarter */
export interface StockQuarterAnalysis {
  ticker: string;
  company: string;
  totalValue: number;
  totalDeltaValue: number;
  maxPortfolioPct: number;
  avgPortfolioPct: number;
  buyerCount: number;
  sellerCount: number;
  holderCount: number;
  newHolderCount: number;
  closeCount: number;
  highConvictionCount: number;
  netBuyers: number;
  buyerSellerRatio: number;
  ownershipDeltaAvg: number;
  fundConcentrationAvg: number;
  delta: number; // percentage or Infinity for all-new
  /** On-the-fly 1-10 institutional composite (see lib/smartScore); set by the quarter loaders. */
  smartScore?: number;
  scoreBreadth?: number | null;
  scoreMomentum?: number | null;
  scoreConviction?: number | null;
}

/**
 * Numeric keys of StockQuarterAnalysis — the only fields the strategy screens
 * and analysis tables may sort or filter on. Typing sort keys with this union
 * makes a string-valued or misspelled sort key a compile error.
 */
export type NumericStockKey = {
  [K in keyof StockQuarterAnalysis]-?: NonNullable<StockQuarterAnalysis[K]> extends number
    ? K
    : never;
}[keyof StockQuarterAnalysis];

// ---------- Enriched Non-Quarterly Filings ----------

export interface EnrichedNQFiling extends NonQuarterlyFiling {
  quarterShares: number | null; // shares in latest 13F (null = fund not found)
  deltaShares: number | null; // nq shares - quarter shares
  deltaType: "NEW" | "INCREASE" | "DECREASE" | "CLOSED" | "NO CHANGE" | "UNKNOWN";
  deltaPct: number | null; // percentage change vs quarter
  quarterPortfolioPct: number | null;
  /** For NEW positions: weight over the fund's merged portfolio (13F total + this position). */
  estimatedPortfolioPct: number | null;
}

/** A fund's latest-13F view: per-ticker positions plus the filing's declared total value. */
export interface FundQuarterSnapshot {
  tickerMap: Map<string, { shares: number; portfolioPct: number }>;
  totalValue: number;
}
