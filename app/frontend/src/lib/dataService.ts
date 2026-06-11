import Papa from "papaparse";
import { DATABASE_URL, IS_GH_PAGES_MODE, BASE_PATH } from "./config";
import { parseQuarters, type Quarter } from "./quarters";

export type { Quarter } from "./quarters";

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

// ---------- Parsed domain types ----------

export interface HedgeFund {
  cik: string;
  fund: string;
  manager: string;
  denomination: string;
  ciks: string;
  url: string;
}

export interface Stock {
  cusip: string;
  ticker: string;
  company: string;
  sector?: string;
  industry?: string;
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
}

// ---------- CSV fetch + parse helper ----------

async function fetchCSV<T>(url: string): Promise<T[]> {
  const fullUrl = IS_GH_PAGES_MODE
    ? `${BASE_PATH}${url}`
    : `${DATABASE_URL}${url.replace(/^\/database/, "")}`;
  const response = await fetch(fullUrl);
  if (!response.ok) throw new Error(`Failed to fetch ${url}: ${response.status}`);
  const text = await response.text();

  return new Promise((resolve, reject) => {
    Papa.parse<T>(text, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => resolve(results.data),
      error: (err: Error) => reject(err),
    });
  });
}

// ---------- Simple in-memory cache ----------

const cache = new Map<string, { data: unknown; ts: number }>();
const CACHE_TTL = 10 * 60 * 1000; // 10 minutes

async function cachedFetch<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const cached = cache.get(key);
  if (cached && Date.now() - cached.ts < CACHE_TTL) return cached.data as T;
  const data = await fetcher();
  cache.set(key, { data, ts: Date.now() });
  return data;
}

// ---------- Value parsing helpers ----------

export function parseValueString(v: string): number {
  if (!v || v === "N/A") return 0;
  const cleaned = v.replace(/[,$]/g, "");
  const match = cleaned.match(/^(-?[\d.]+)([BMK])?$/i);
  if (!match) return parseFloat(cleaned) || 0;
  const num = parseFloat(match[1]);
  const suffix = (match[2] || "").toUpperCase();
  if (suffix === "B") return num * 1_000_000_000;
  if (suffix === "M") return num * 1_000_000;
  if (suffix === "K") return num * 1_000;
  return num;
}

export function formatValue(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

export function formatPct(n: number, showSign = false): string {
  if (!isFinite(n)) return "NEW";
  const sign = showSign && n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

/**
 * Formats a number as a compact, no-dollar magnitude string (e.g. "113.69M",
 * "518.8K"), trimming trailing zeros. Mirrors the Python `format_value` style
 * used when writing the per-quarter CSVs, so aggregated rows render identically
 * to the source data.
 */
function formatValueShort(n: number): string {
  const trim = (x: number) => parseFloat(x.toFixed(2)).toString();
  const abs = Math.abs(n);
  if (abs >= 1e12) return `${trim(n / 1e12)}T`;
  if (abs >= 1e9) return `${trim(n / 1e9)}B`;
  if (abs >= 1e6) return `${trim(n / 1e6)}M`;
  if (abs >= 1e3) return `${trim(n / 1e3)}K`;
  return trim(n);
}

/**
 * Aggregates per-CUSIP holdings into one row per ticker.
 *
 * A fund can report the same ticker under several CUSIPs (e.g. common stock
 * plus a 13F-reportable convertible note, or multiple share classes). The
 * per-ticker views — stock page, multi-fund consensus, and the CLI fund
 * analysis — all collapse these into a single line; this helper gives the
 * fund-portfolio view the same behaviour. Shares, deltas, values and portfolio
 * percentages are summed, and the Δ label is recomputed from the aggregated
 * shares. Tickers backed by a single CUSIP are returned unchanged so their
 * original formatting is preserved exactly. The synthetic "Total" row is
 * dropped.
 */
export function aggregateHoldingsByTicker(holdings: QuarterlyHolding[]): QuarterlyHolding[] {
  const groups = new Map<
    string,
    { base: QuarterlyHolding; value: number; deltaValue: number; count: number }
  >();

  for (const h of holdings) {
    if (h.cusip === "Total") continue;
    const value = parseValueString(h.value);
    const deltaValue = parseValueString(h.deltaValue);
    const existing = groups.get(h.ticker);
    if (existing) {
      existing.base.shares += h.shares;
      existing.base.deltaShares += h.deltaShares;
      existing.base.portfolioPct += h.portfolioPct;
      existing.value += value;
      existing.deltaValue += deltaValue;
      existing.count += 1;
    } else {
      groups.set(h.ticker, { base: { ...h }, value, deltaValue, count: 1 });
    }
  }

  return [...groups.values()].map(({ base, value, deltaValue, count }) => {
    if (count === 1) return base;
    const prevShares = base.shares - base.deltaShares;
    let delta: string;
    if (base.shares === 0) delta = "CLOSE";
    else if (base.deltaShares === 0) delta = "NO CHANGE";
    else if (base.shares === base.deltaShares) delta = "NEW";
    else delta = formatPct(prevShares > 0 ? (base.deltaShares / prevShares) * 100 : 0, true);
    return {
      ...base,
      value: formatValueShort(value),
      deltaValue: formatValueShort(deltaValue),
      delta,
    };
  });
}

// ---------- Public API: basic data ----------

function rawToFund(r: RawHedgeFund): HedgeFund {
  return {
    cik: r.CIK,
    fund: r.Fund,
    manager: r.Manager,
    denomination: r.Denomination,
    ciks: r.CIKs,
    url: r.URL || "",
  };
}

export async function getHedgeFunds(): Promise<HedgeFund[]> {
  return cachedFetch("hedge_funds", async () => {
    const raw = await fetchCSV<RawHedgeFund>("/database/hedge_funds.csv");
    return raw.map(rawToFund);
  });
}

export type ExcludedHedgeFund = HedgeFund;

export async function getExcludedHedgeFunds(): Promise<ExcludedHedgeFund[]> {
  return cachedFetch("excluded_hedge_funds", async () => {
    const raw = await fetchCSV<RawHedgeFund>("/database/excluded_hedge_funds.csv");
    return raw.map(rawToFund);
  });
}

const FUNDS_CSV_HEADER = '"CIK","Fund","Manager","Denomination","CIKs","URL"';

/** Quotes a CSV field, doubling embedded double quotes per RFC 4180. */
function csvQuote(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function fundsToCSV(funds: HedgeFund[]): string {
  const sorted = [...funds].sort((a, b) =>
    a.fund.localeCompare(b.fund, undefined, { sensitivity: "base" }),
  );
  return (
    FUNDS_CSV_HEADER +
    "\n" +
    sorted
      .map((f) => [f.cik, f.fund, f.manager, f.denomination, f.ciks, f.url].map(csvQuote).join(","))
      .join("\n") +
    "\n"
  );
}

/**
 * Generates a hedge_funds CSV string from an array of funds.
 */
export function generateHedgeFundsCSV(allFunds: HedgeFund[]): string {
  return fundsToCSV(allFunds);
}

/**
 * Generates an excluded_hedge_funds CSV string from an array of excluded funds.
 */
export function generateExcludedFundsCSV(allExcluded: ExcludedHedgeFund[]): string {
  return fundsToCSV(allExcluded);
}

/**
 * Generates updated hedge_funds CSV after adding a new fund.
 */
export function generateAddFundCSV(allFunds: HedgeFund[], newFund: HedgeFund): string {
  return fundsToCSV([...allFunds, newFund]);
}

/**
 * Generates updated CSVs after moving a fund from hedge_funds to excluded.
 */
export function generateDeleteFundCSVs(
  allFunds: HedgeFund[],
  excludedFunds: ExcludedHedgeFund[],
  fundToDelete: HedgeFund,
): { hedgeFundsCSV: string; excludedCSV: string } {
  const remaining = allFunds.filter((f) => f.cik !== fundToDelete.cik);
  const allExcluded = [...excludedFunds, fundToDelete];
  return {
    hedgeFundsCSV: fundsToCSV(remaining),
    excludedCSV: fundsToCSV(allExcluded),
  };
}

/**
 * Generates updated CSVs after restoring an excluded fund back to hedge_funds.
 */
export function generateRestoreFundCSVs(
  allFunds: HedgeFund[],
  excludedFunds: ExcludedHedgeFund[],
  fundToRestore: ExcludedHedgeFund,
): { hedgeFundsCSV: string; excludedCSV: string } {
  const updatedFunds = [...allFunds, fundToRestore];
  const remaining = excludedFunds.filter((f) => f.cik !== fundToRestore.cik);
  return {
    hedgeFundsCSV: fundsToCSV(updatedFunds),
    excludedCSV: fundsToCSV(remaining),
  };
}

export const MODEL_PROVIDERS = ["GitHub", "Groq", "Google", "HuggingFace", "OpenRouter"] as const;

/** Display names for CSV client values (used in UI only) */
export const PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  GitHub: "GitHub Models",
  Google: "Google AI Studio",
  Groq: "Groq",
  HuggingFace: "HuggingFace",
  OpenRouter: "OpenRouter",
};
export type ModelProvider = (typeof MODEL_PROVIDERS)[number];

export function generateModelsCSV(models: AIModel[]): string {
  return (
    '"ID","Description","Client"\n' +
    models.map((m) => `"${m.id}","${m.description}","${m.client}"`).join("\n") +
    "\n"
  );
}

export async function saveFileToDisk(content: string, filePath: string): Promise<void> {
  if (IS_GH_PAGES_MODE) {
    // In GitHub Pages mode, download the file instead of saving to server
    downloadFile(content, filePath.split("/").pop() || filePath);
    return;
  }
  const res = await fetch(`${window.location.origin}/database/${filePath}`, {
    method: "PUT",
    headers: { "Content-Type": "text/plain" },
    body: content,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Unknown error" }));
    throw new Error(err.error || "Failed to save file");
  }
}

/** @deprecated Use saveFileToDisk instead */
export function downloadFile(content: string, filename: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function clearCache(key?: string) {
  if (key) {
    cache.delete(key);
  } else {
    cache.clear();
  }
}

export async function getStocks(): Promise<Stock[]> {
  return cachedFetch("stocks", async () => {
    const [raw, hierarchy] = await Promise.all([
      fetchCSV<RawStock>("/database/stocks.csv"),
      getSectorHierarchy(),
    ]);
    // Derive the Sector from the Industry via sector_hierarchy.csv —
    // stocks.csv intentionally stores only the Industry to avoid duplication.
    const industryToSector = new Map(hierarchy.map((h) => [h.industry, h.sector]));
    return raw.map((r) => ({
      cusip: r.CUSIP,
      ticker: r.Ticker,
      company: r.Company,
      industry: r.Industry || undefined,
      sector: r.Industry ? industryToSector.get(r.Industry) : undefined,
    }));
  });
}

export async function getNonQuarterlyFilings(): Promise<NonQuarterlyFiling[]> {
  return cachedFetch("non_quarterly", async () => {
    const raw = await fetchCSV<RawNonQuarterly>("/database/non_quarterly.csv");
    return raw.map((r) => ({
      fund: r.Fund,
      cusip: r.CUSIP,
      ticker: r.Ticker,
      company: r.Company,
      shares: parseInt(r.Shares, 10) || 0,
      value: r.Value,
      avgPrice: r.Avg_Price,
      date: r.Date,
      filingDate: r.Filing_Date,
    }));
  });
}

export async function getModels(): Promise<AIModel[]> {
  return cachedFetch("models", async () => {
    const raw = await fetchCSV<RawModel>("/database/models.csv");
    return raw.map((r) => ({
      id: r.ID,
      description: r.Description,
      client: r.Client,
    }));
  });
}

export interface SectorHierarchyEntry {
  sector: string;
  industry: string;
  count: number;
}

export async function getSectorHierarchy(): Promise<SectorHierarchyEntry[]> {
  return cachedFetch("sector_hierarchy", async () => {
    const raw = await fetchCSV<RawSectorHierarchy>("/database/sector_hierarchy.csv");
    return raw.map((r) => ({
      sector: r.Sector,
      industry: r.Industry,
      count: parseInt(r.Count, 10) || 0,
    }));
  });
}

/**
 * Fetches the list of available quarter folders, sorted chronologically.
 * Derives from /api/database/quarters locally or metadata.json in GH Pages mode.
 */
export async function getAvailableQuarters(): Promise<readonly Quarter[]> {
  if (IS_GH_PAGES_MODE) {
    const response = await fetch(`${BASE_PATH}/database/metadata.json`);
    if (!response.ok) throw new Error("Failed to load metadata.json");
    const metadata: { quarters?: string[] } = await response.json();
    return parseQuarters(metadata.quarters ?? []);
  }
  const response = await fetch(`${window.location.origin}/api/database/quarters`);
  if (!response.ok) throw new Error("Failed to list quarters");
  const raw: string[] = await response.json();
  return parseQuarters(raw);
}

/**
 * Fetch the pre-aggregated quarter analysis from the backend (single request).
 *
 * Returns null in GH Pages mode (no backend); callers should fall back to the
 * client-side `runQuarterAnalysis` which fetches each fund CSV individually.
 */
export async function fetchQuarterAnalysis(
  quarter: string,
): Promise<readonly StockQuarterAnalysis[] | null> {
  if (IS_GH_PAGES_MODE) return null;
  const url = `${window.location.origin}/api/database/quarters/${encodeURIComponent(quarter)}/analysis`;
  const response = await fetch(url);
  if (!response.ok) throw new Error("Failed to fetch quarter analysis");
  interface RawAnalysisRow {
    Ticker?: string;
    Company?: string;
    Total_Value?: number;
    Total_Delta_Value?: number;
    Max_Portfolio_Pct?: number;
    Avg_Portfolio_Pct?: number;
    Buyer_Count?: number;
    Seller_Count?: number;
    Holder_Count?: number;
    New_Holder_Count?: number;
    Close_Count?: number;
    High_Conviction_Count?: number;
    Net_Buyers?: number;
    Buyer_Seller_Ratio?: number;
    Ownership_Delta_Avg?: number;
    Avg_Fund_Concentration?: number;
    Delta?: number;
  }
  const raw = (await response.json()) as RawAnalysisRow[];
  return raw.map((r) => ({
    ticker: r.Ticker ?? "",
    company: r.Company ?? "",
    totalValue: r.Total_Value ?? 0,
    totalDeltaValue: r.Total_Delta_Value ?? 0,
    maxPortfolioPct: r.Max_Portfolio_Pct ?? 0,
    avgPortfolioPct: r.Avg_Portfolio_Pct ?? 0,
    buyerCount: r.Buyer_Count ?? 0,
    sellerCount: r.Seller_Count ?? 0,
    holderCount: r.Holder_Count ?? 0,
    newHolderCount: r.New_Holder_Count ?? 0,
    closeCount: r.Close_Count ?? 0,
    highConvictionCount: r.High_Conviction_Count ?? 0,
    netBuyers: r.Net_Buyers ?? 0,
    buyerSellerRatio: r.Buyer_Seller_Ratio ?? 0,
    ownershipDeltaAvg: r.Ownership_Delta_Avg ?? 0,
    fundConcentrationAvg: r.Avg_Fund_Concentration ?? 0,
    delta: r.Delta ?? 0,
  }));
}

/**
 * Returns the most recent quarter as resolved by the backend, or null if none exist.
 * Backend is the single source of truth; frontend does not sort the quarter list itself.
 * Caching is intentionally delegated to react-query at the call site.
 */
export async function getLatestQuarter(): Promise<Quarter | null> {
  if (IS_GH_PAGES_MODE) {
    const quarters = await getAvailableQuarters();
    return quarters.at(-1) ?? null;
  }
  const response = await fetch(`${window.location.origin}/api/database/quarters/latest`);
  if (!response.ok) throw new Error("Failed to fetch latest quarter");
  const data: { quarter: string | null } = await response.json();
  if (!data.quarter) return null;
  return parseQuarters([data.quarter])[0] ?? null;
}

/** Converts a fund name to its filename form (spaces → underscores). */
function fundNameToFileName(name: string): string {
  return name.replace(/ /g, "_");
}

/** Converts a filename form back to fund name (underscores → spaces). */
function fileNameToFundName(name: string): string {
  return name.replace(/_/g, " ");
}

/** Returns only the quarters where a specific fund has data (sorted chronologically). */
export async function getFundAvailableQuarters(fundName: string): Promise<Quarter[]> {
  return cachedFetch(`fund_quarters_${fundName}`, async () => {
    const fileName = fundNameToFileName(fundName);
    const quarters = await getAvailableQuarters();
    const results = await Promise.all(
      quarters.map(async (q) => {
        try {
          const fundList = await getQuarterFundList(q);
          return fundList.includes(fileName) ? q : null;
        } catch {
          return null;
        }
      }),
    );
    return results.filter((q): q is Quarter => q !== null);
  });
}

export async function getQuarterFundList(quarter: string): Promise<string[]> {
  return cachedFetch(`quarter_funds_${quarter}`, async () => {
    if (IS_GH_PAGES_MODE) {
      // In GH Pages mode, read from bundled manifest.json
      const response = await fetch(`${BASE_PATH}/database/${quarter}/manifest.json`);
      if (!response.ok) throw new Error(`No data available for ${quarter}`);
      return response.json();
    }
    const response = await fetch(`${window.location.origin}/api/database/quarters/${quarter}`);
    if (!response.ok) throw new Error(`Failed to list funds for ${quarter}`);
    const files: string[] = await response.json();
    return files;
  });
}

export async function getFundQuarterlyHoldings(
  quarter: string,
  fundName: string,
): Promise<QuarterlyHolding[]> {
  const key = `holdings_${quarter}_${fundName}`;
  return cachedFetch(key, async () => {
    const raw = await fetchCSV<RawQuarterlyHolding>(
      `/database/${quarter}/${encodeURIComponent(fundNameToFileName(fundName))}.csv`,
    );
    return raw.map((r) => ({
      cusip: r.CUSIP,
      ticker: r.Ticker,
      company: r.Company,
      shares: parseInt(r.Shares, 10) || 0,
      deltaShares: r.Delta_Shares === "" ? 0 : parseInt(r.Delta_Shares, 10) || 0,
      value: r.Value,
      deltaValue: r.Delta_Value,
      delta: r.Delta,
      portfolioPct: parseFloat(r["Portfolio%"]) || 0,
    }));
  });
}

// ---------- Analysis: Quarter Analysis (replicates Python quarter_analysis) ----------

/**
 * Loads all fund CSVs for a quarter, aggregates by Fund+Ticker,
 * then aggregates to stock-level with buyer/seller counts etc.
 * Progress callback reports loading status.
 */
export async function runQuarterAnalysis(
  quarter: string,
  onProgress?: (msg: string, pct: number) => void,
  fundFilter?: Set<string>,
): Promise<StockQuarterAnalysis[]> {
  const cacheKey =
    fundFilter && fundFilter.size > 0
      ? `quarter_analysis_${quarter}_funds_${[...fundFilter].sort().join(",")}`
      : `quarter_analysis_${quarter}`;
  return cachedFetch(cacheKey, async () => {
    onProgress?.("Fetching fund list…", 5);
    const [allFundNames, stocks] = await Promise.all([getQuarterFundList(quarter), getStocks()]);
    const fundNames =
      fundFilter && fundFilter.size > 0
        ? allFundNames.filter((fn) => fundFilter.has(fileNameToFundName(fn)))
        : allFundNames;
    const tickerNameMap = new Map(stocks.map((s) => [s.ticker, s.company]));
    onProgress?.(`Loading ${fundNames.length} funds…`, 10);

    // Load all fund CSVs in parallel (batched to avoid rate limits)
    const batchSize = 20;
    const allHoldings: { fund: string; h: QuarterlyHolding }[] = [];

    for (let i = 0; i < fundNames.length; i += batchSize) {
      const batch = fundNames.slice(i, i + batchSize);
      const results = await Promise.all(
        batch.map(async (fileName) => {
          try {
            const holdings = await getFundQuarterlyHoldings(quarter, fileNameToFundName(fileName));
            return holdings
              .filter((h) => h.cusip !== "Total")
              .map((h) => ({ fund: fileNameToFundName(fileName), h }));
          } catch {
            return [];
          }
        }),
      );
      results.forEach((r) => allHoldings.push(...r));
      const pct = Math.round(10 + (i / fundNames.length) * 70);
      onProgress?.(
        `Loaded ${Math.min(i + batchSize, fundNames.length)}/${fundNames.length} funds`,
        pct,
      );
    }

    onProgress?.("Aggregating data…", 85);

    // Step 1: Aggregate by Fund+Ticker (multiple CUSIPs → single entry)
    const fundTickerMap = new Map<string, FundTickerHolding>();

    for (const { fund, h } of allHoldings) {
      const key = `${fund}||${h.ticker}`;
      const existing = fundTickerMap.get(key);
      const valueNum = parseValueString(h.value);
      const deltaValueNum = parseValueString(h.deltaValue);

      if (existing) {
        existing.shares += h.shares;
        existing.deltaShares += h.deltaShares;
        existing.value += valueNum;
        existing.deltaValue += deltaValueNum;
        existing.portfolioPct += h.portfolioPct;
      } else {
        fundTickerMap.set(key, {
          fund,
          ticker: h.ticker,
          company: tickerNameMap.get(h.ticker) || h.company,
          shares: h.shares,
          deltaShares: h.deltaShares,
          value: valueNum,
          deltaValue: deltaValueNum,
          portfolioPct: h.portfolioPct,
          portfolioPctRank: 0,
          sharesDeltaPct: 0,
          fundConcentrationRatio: 0,
          delta: h.delta,
          isBuyer: false,
          isSeller: false,
          isHolder: false,
          isNew: false,
          isClosed: false,
          isHighConviction: false,
        });
      }
    }

    // Step 2: Calculate flags (replicates _calculate_fund_level_flags)
    // First compute portfolio rank per fund
    const fundGroups = new Map<string, FundTickerHolding[]>();
    for (const fth of fundTickerMap.values()) {
      const arr = fundGroups.get(fth.fund) || [];
      arr.push(fth);
      fundGroups.set(fth.fund, arr);
    }

    for (const holdings of fundGroups.values()) {
      // Sort by portfolioPct descending to assign rank
      const sorted = [...holdings].sort((a, b) => b.portfolioPct - a.portfolioPct);
      // Fund concentration: sum of top 10 positions
      const top10Sum = sorted.slice(0, 10).reduce((s, h) => s + h.portfolioPct, 0);

      sorted.forEach((fth, idx) => {
        const rank = idx + 1;
        fth.portfolioPctRank = rank;
        fth.fundConcentrationRatio = top10Sum;
        fth.isBuyer = fth.deltaValue > 0;
        fth.isSeller = fth.deltaValue < 0;
        fth.isHolder = fth.shares > 0;
        fth.isNew = fth.shares > 0 && fth.shares === fth.deltaShares;
        fth.isClosed = fth.shares === 0;
        fth.isHighConviction = fth.isNew && (rank <= 10 || fth.portfolioPct > 3.0);

        // Shares delta pct (velocity of accumulation, only for existing positions)
        const prevShares = fth.shares - fth.deltaShares;
        fth.sharesDeltaPct =
          prevShares > 0 && fth.shares > 0 ? (fth.deltaShares / prevShares) * 100 : 0;
      });
    }

    // Step 3: Aggregate to stock level (replicates _aggregate_stock_data)
    interface StockQuarterAccumulator extends StockQuarterAnalysis {
      _sumPct?: number;
      _countPct?: number;
      _sumConcentration?: number;
      _sumDeltaPct?: number;
      _countDeltaPct?: number;
    }
    const stockMap = new Map<string, StockQuarterAccumulator>();

    for (const fth of fundTickerMap.values()) {
      const existing = stockMap.get(fth.ticker);
      if (existing) {
        existing.totalValue += fth.value;
        existing.totalDeltaValue += fth.deltaValue;
        existing.maxPortfolioPct = Math.max(existing.maxPortfolioPct, fth.portfolioPct);
        existing._sumPct += fth.portfolioPct;
        existing._countPct += 1;
        existing._sumConcentration += fth.fundConcentrationRatio;
        existing.buyerCount += fth.isBuyer ? 1 : 0;
        existing.sellerCount += fth.isSeller ? 1 : 0;
        existing.holderCount += fth.isHolder ? 1 : 0;
        existing.newHolderCount += fth.isNew ? 1 : 0;
        existing.closeCount += fth.isClosed ? 1 : 0;
        existing.highConvictionCount += fth.isHighConviction ? 1 : 0;
        // Accumulation velocity: only buyers who aren't new
        if (fth.isBuyer && !fth.isNew && fth.sharesDeltaPct !== 0) {
          existing._sumDeltaPct += fth.sharesDeltaPct;
          existing._countDeltaPct += 1;
        }
      } else {
        const isBuyerNotNew = fth.isBuyer && !fth.isNew && fth.sharesDeltaPct !== 0;
        stockMap.set(fth.ticker, {
          ticker: fth.ticker,
          company: tickerNameMap.get(fth.ticker) || fth.company,
          totalValue: fth.value,
          totalDeltaValue: fth.deltaValue,
          maxPortfolioPct: fth.portfolioPct,
          avgPortfolioPct: 0,
          buyerCount: fth.isBuyer ? 1 : 0,
          sellerCount: fth.isSeller ? 1 : 0,
          holderCount: fth.isHolder ? 1 : 0,
          newHolderCount: fth.isNew ? 1 : 0,
          closeCount: fth.isClosed ? 1 : 0,
          highConvictionCount: fth.isHighConviction ? 1 : 0,
          netBuyers: 0,
          buyerSellerRatio: 0,
          ownershipDeltaAvg: 0,
          fundConcentrationAvg: 0,
          delta: 0,
          _sumPct: fth.portfolioPct,
          _countPct: 1,
          _sumConcentration: fth.fundConcentrationRatio,
          _sumDeltaPct: isBuyerNotNew ? fth.sharesDeltaPct : 0,
          _countDeltaPct: isBuyerNotNew ? 1 : 0,
        });
      }
    }

    // Step 4: Derived metrics (replicates _calculate_derived_metrics)
    const results: StockQuarterAnalysis[] = [];
    for (const s of stockMap.values()) {
      s.avgPortfolioPct = s._countPct > 0 ? s._sumPct / s._countPct : 0;
      s.netBuyers = s.buyerCount - s.sellerCount;
      s.buyerSellerRatio = s.sellerCount > 0 ? s.buyerCount / s.sellerCount : Infinity;
      s.ownershipDeltaAvg = s._countDeltaPct > 0 ? s._sumDeltaPct / s._countDeltaPct : 0;
      s.fundConcentrationAvg = s._countPct > 0 ? s._sumConcentration / s._countPct : 0;

      const previousTotal = s.totalValue - s.totalDeltaValue;
      if (s.newHolderCount === s.holderCount && s.closeCount === 0) {
        s.delta = Infinity;
      } else if (previousTotal !== 0) {
        s.delta = (s.totalDeltaValue / previousTotal) * 100;
      } else {
        s.delta = 0;
      }

      delete s._sumPct;
      delete s._countPct;
      delete s._sumConcentration;
      delete s._sumDeltaPct;
      delete s._countDeltaPct;
      results.push(s);
    }

    onProgress?.("Done", 100);
    return results;
  });
}

// ---------- Analysis: Stock Analysis (replicates Python stock_analysis) ----------

/**
 * Returns all fund-level holdings for a specific ticker in a quarter.
 */
export async function runStockAnalysis(
  ticker: string,
  quarter: string,
  onProgress?: (msg: string, pct: number) => void,
): Promise<FundTickerHolding[]> {
  const key = `stock_analysis_${quarter}_${ticker}`;
  return cachedFetch(key, async () => {
    onProgress?.("Fetching fund list…", 5);
    const [fundNames, stocks] = await Promise.all([getQuarterFundList(quarter), getStocks()]);
    const tickerNameMap = new Map(stocks.map((s) => [s.ticker, s.company]));
    onProgress?.(`Scanning ${fundNames.length} funds for ${ticker}…`, 10);

    const batchSize = 20;
    const results: FundTickerHolding[] = [];

    for (let i = 0; i < fundNames.length; i += batchSize) {
      const batch = fundNames.slice(i, i + batchSize);
      const batchResults = await Promise.all(
        batch.map(async (fileName) => {
          try {
            const fundName = fileNameToFundName(fileName);
            const holdings = await getFundQuarterlyHoldings(quarter, fundName);
            // Filter for this ticker, aggregate across CUSIPs
            const tickerHoldings = holdings.filter(
              (h) => h.ticker === ticker && h.cusip !== "Total",
            );
            if (tickerHoldings.length === 0) return null;

            let shares = 0,
              deltaShares = 0,
              value = 0,
              deltaValue = 0,
              portfolioPct = 0;
            const company = tickerNameMap.get(ticker) || tickerHoldings[0].company;

            for (const h of tickerHoldings) {
              shares += h.shares;
              deltaShares += h.deltaShares;
              value += parseValueString(h.value);
              deltaValue += parseValueString(h.deltaValue);
              portfolioPct += h.portfolioPct;
            }

            const isNew = shares > 0 && shares === deltaShares;
            const isClosed = shares === 0;

            // Compute delta string
            let delta: string;
            if (isClosed) delta = "CLOSE";
            else if (isNew) delta = "NEW";
            else if (deltaShares === 0) delta = "NO CHANGE";
            else {
              const prev = shares - deltaShares;
              delta = prev !== 0 ? formatPct((deltaShares / prev) * 100, true) : "NEW";
            }

            const prevShares = shares - deltaShares;
            const sharesDeltaPctVal =
              prevShares > 0 && shares > 0 ? (deltaShares / prevShares) * 100 : 0;

            return {
              fund: fundName,
              ticker,
              company,
              shares,
              deltaShares,
              value,
              deltaValue,
              portfolioPct,
              portfolioPctRank: 0,
              sharesDeltaPct: sharesDeltaPctVal,
              fundConcentrationRatio: 0,
              delta,
              isBuyer: deltaValue > 0,
              isSeller: deltaValue < 0,
              isHolder: shares > 0,
              isNew,
              isClosed,
              isHighConviction: false,
            } as FundTickerHolding;
          } catch {
            return null;
          }
        }),
      );
      batchResults.forEach((r) => {
        if (r) results.push(r);
      });
      const pct = Math.round(10 + (i / fundNames.length) * 85);
      onProgress?.(
        `Scanned ${Math.min(i + batchSize, fundNames.length)}/${fundNames.length} funds`,
        pct,
      );
    }

    onProgress?.("Done", 100);
    return results.sort((a, b) => b.shares - a.shares);
  });
}

// ---------- Analysis: Fund Analysis (replicates Python fund_analysis) ----------

/**
 * Returns all holdings for a specific fund in a quarter, aggregated by ticker.
 */
export async function runFundAnalysis(
  fundName: string,
  quarter: string,
  onProgress?: (msg: string, pct: number) => void,
): Promise<FundTickerHolding[]> {
  const key = `fund_analysis_${quarter}_${fundName}`;
  return cachedFetch(key, async () => {
    onProgress?.("Loading fund holdings…", 10);
    const [holdings, stocks] = await Promise.all([
      getFundQuarterlyHoldings(quarter, fundName),
      getStocks(),
    ]);
    const tickerNameMap = new Map(stocks.map((s) => [s.ticker, s.company]));

    onProgress?.("Aggregating by ticker…", 50);

    // Aggregate by ticker (multiple CUSIPs → single entry)
    const tickerMap = new Map<string, FundTickerHolding>();
    for (const h of holdings) {
      if (h.cusip === "Total") continue;
      const existing = tickerMap.get(h.ticker);
      const valueNum = parseValueString(h.value);
      const deltaValueNum = parseValueString(h.deltaValue);

      if (existing) {
        existing.shares += h.shares;
        existing.deltaShares += h.deltaShares;
        existing.value += valueNum;
        existing.deltaValue += deltaValueNum;
        existing.portfolioPct += h.portfolioPct;
      } else {
        tickerMap.set(h.ticker, {
          fund: fundName,
          ticker: h.ticker,
          company: tickerNameMap.get(h.ticker) || h.company,
          shares: h.shares,
          deltaShares: h.deltaShares,
          value: valueNum,
          deltaValue: deltaValueNum,
          portfolioPct: h.portfolioPct,
          portfolioPctRank: 0,
          sharesDeltaPct: 0,
          fundConcentrationRatio: 0,
          delta: h.delta,
          isBuyer: false,
          isSeller: false,
          isHolder: false,
          isNew: false,
          isClosed: false,
          isHighConviction: false,
        });
      }
    }

    // Calculate flags and ranks
    const allHoldings = [...tickerMap.values()];
    allHoldings.sort((a, b) => b.portfolioPct - a.portfolioPct);
    const top10Sum = allHoldings.slice(0, 10).reduce((s, h) => s + h.portfolioPct, 0);

    allHoldings.forEach((fth, idx) => {
      const rank = idx + 1;
      fth.portfolioPctRank = rank;
      fth.fundConcentrationRatio = top10Sum;
      fth.isBuyer = fth.deltaValue > 0;
      fth.isSeller = fth.deltaValue < 0;
      fth.isHolder = fth.shares > 0;
      fth.isNew = fth.shares > 0 && fth.shares === fth.deltaShares;
      fth.isClosed = fth.shares === 0;
      fth.isHighConviction = fth.isNew && (rank <= 10 || fth.portfolioPct > 3.0);
      const prevShares = fth.shares - fth.deltaShares;
      fth.sharesDeltaPct =
        prevShares > 0 && fth.shares > 0 ? (fth.deltaShares / prevShares) * 100 : 0;

      // Recalculate delta string from aggregated values
      if (fth.shares === 0) fth.delta = "CLOSE";
      else if (fth.deltaShares === 0) fth.delta = "NO CHANGE";
      else if (fth.shares > 0 && fth.shares === fth.deltaShares) fth.delta = "NEW";
      else if (prevShares > 0) fth.delta = formatPct((fth.deltaShares / prevShares) * 100, true);
    });

    onProgress?.("Done", 100);
    return allHoldings;
  });
}

// ---------- Enriched Non-Quarterly Filings (join with latest quarter) ----------

export interface EnrichedNQFiling extends NonQuarterlyFiling {
  quarterShares: number | null; // shares in latest 13F (null = fund not found)
  deltaShares: number | null; // nq shares - quarter shares
  deltaType: "NEW" | "INCREASE" | "DECREASE" | "CLOSED" | "NO CHANGE" | "UNKNOWN";
  deltaPct: number | null; // percentage change vs quarter
  quarterPortfolioPct: number | null;
}

/**
 * Enriches non-quarterly filings with last-quarter data.
 * For each NQ filing, looks up the fund's holdings in the latest available quarter
 * and computes the delta (new position vs quarterly position).
 */
export async function getEnrichedNQFilings(
  onProgress?: (msg: string, pct: number) => void,
): Promise<EnrichedNQFiling[]> {
  return cachedFetch("enriched_nq", async () => {
    onProgress?.("Loading filings…", 5);
    const allFilings = await getNonQuarterlyFilings();

    // Deduplicate: keep only the latest filing per Fund+Ticker
    const latestMap = new Map<string, NonQuarterlyFiling>();
    for (const f of allFilings) {
      const key = `${f.fund}||${f.ticker}`;
      const existing = latestMap.get(key);
      if (
        !existing ||
        f.date > existing.date ||
        (f.date === existing.date && f.filingDate > existing.filingDate)
      ) {
        latestMap.set(key, f);
      }
    }
    const filings = [...latestMap.values()];

    onProgress?.("Resolving per-fund latest quarter…", 10);

    // Get unique fund names from filings
    const uniqueFunds = [...new Set(filings.map((f) => f.fund))];

    // Load quarterly holdings for each fund using its OWN latest quarter (which may be
    // older than the overall latest quarter, e.g. early in a Q1 13F filing window).
    // Map: fund → ticker → { shares, portfolioPct } (aggregated across CUSIPs)
    const fundQuarterlyMap = new Map<
      string,
      Map<string, { shares: number; portfolioPct: number }>
    >();
    const batchSize = 10;

    for (let i = 0; i < uniqueFunds.length; i += batchSize) {
      const batch = uniqueFunds.slice(i, i + batchSize);
      const results = await Promise.all(
        batch.map(async (fundName) => {
          try {
            const fundQuarters = await getFundAvailableQuarters(fundName);
            const fundLatest = fundQuarters[fundQuarters.length - 1];
            if (!fundLatest) {
              return {
                fundName,
                tickerMap: new Map<string, { shares: number; portfolioPct: number }>(),
              };
            }
            const holdings = await getFundQuarterlyHoldings(fundLatest, fundName);
            const tickerMap = new Map<string, { shares: number; portfolioPct: number }>();
            for (const h of holdings) {
              if (h.cusip !== "Total" && h.ticker) {
                const existing = tickerMap.get(h.ticker);
                if (existing) {
                  existing.shares += h.shares;
                  existing.portfolioPct += h.portfolioPct;
                } else {
                  tickerMap.set(h.ticker, { shares: h.shares, portfolioPct: h.portfolioPct });
                }
              }
            }
            return { fundName, tickerMap };
          } catch {
            return {
              fundName,
              tickerMap: new Map<string, { shares: number; portfolioPct: number }>(),
            };
          }
        }),
      );
      for (const { fundName, tickerMap } of results) {
        fundQuarterlyMap.set(fundName, tickerMap);
      }
      const pct = Math.round(15 + (i / uniqueFunds.length) * 80);
      onProgress?.(
        `Loaded ${Math.min(i + batchSize, uniqueFunds.length)}/${uniqueFunds.length} funds`,
        pct,
      );
    }

    onProgress?.("Computing deltas…", 95);

    // Enrich each filing, filtering out NO CHANGE (delta = 0%)
    const enriched: EnrichedNQFiling[] = [];
    for (const f of filings) {
      const tickerMap = fundQuarterlyMap.get(f.fund);
      let entry: EnrichedNQFiling;

      if (!tickerMap) {
        entry = {
          ...f,
          quarterShares: 0,
          deltaShares: f.shares,
          deltaType: f.shares === 0 ? ("CLOSED" as const) : ("NEW" as const),
          deltaPct: null,
          quarterPortfolioPct: null,
        };
      } else {
        const qHolding = tickerMap.get(f.ticker);
        const qShares = qHolding ? qHolding.shares : 0;
        const qPct = qHolding ? qHolding.portfolioPct : null;
        const nqShares = f.shares;
        const delta = nqShares - qShares;

        let deltaType: EnrichedNQFiling["deltaType"];
        if (nqShares === 0) {
          deltaType = "CLOSED";
        } else if (qShares === 0) {
          deltaType = "NEW";
        } else if (delta > 0) {
          deltaType = "INCREASE";
        } else if (delta < 0) {
          deltaType = "DECREASE";
        } else {
          deltaType = "NO CHANGE";
        }

        const deltaPct = qShares > 0 ? (delta / qShares) * 100 : null;

        entry = {
          ...f,
          quarterShares: qShares,
          deltaShares: delta,
          deltaType,
          deltaPct,
          quarterPortfolioPct: qPct,
        };
      }

      // Filter out NO CHANGE positions (delta = 0%)
      if (entry.deltaType !== "NO CHANGE") {
        enriched.push(entry);
      }
    }

    onProgress?.("Done", 100);
    return enriched;
  });
}

// clearCache is defined above (line ~311)
