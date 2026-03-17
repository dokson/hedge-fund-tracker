import Papa from "papaparse";
import { DATABASE_URL, IS_GH_PAGES_MODE, BASE_PATH, API_BASE } from "./config";

// ---------- Raw CSV row types ----------

export interface RawHedgeFund {
  CIK: string;
  Fund: string;
  Manager: string;
  Denomination: string;
  CIKs: string;
}

export interface RawStock {
  CUSIP: string;
  Ticker: string;
  Company: string;
  Sector?: string;
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

export interface RawGICSHierarchy {
  "Sector Code": string;
  Sector: string;
  "Industry Group Code": string;
  "Industry Group": string;
  "Industry Code": string;
  Industry: string;
  "Sub-Industry Code": string;
  "Sub-Industry": string;
}

// ---------- Parsed domain types ----------

export interface HedgeFund {
  cik: string;
  fund: string;
  manager: string;
  denomination: string;
  ciks: string;
}

export interface Stock {
  cusip: string;
  ticker: string;
  company: string;
  sector?: string;
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

export interface GICSEntry {
  sectorCode: string;
  sector: string;
  industryGroupCode: string;
  industryGroup: string;
  industryCode: string;
  industry: string;
  subIndustryCode: string;
  subIndustry: string;
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

// ---------- Public API: basic data ----------

export async function getHedgeFunds(): Promise<HedgeFund[]> {
  return cachedFetch("hedge_funds", async () => {
    const raw = await fetchCSV<RawHedgeFund>("/database/hedge_funds.csv");
    return raw.map((r) => ({
      cik: r.CIK,
      fund: r.Fund,
      manager: r.Manager,
      denomination: r.Denomination,
      ciks: r.CIKs,
    }));
  });
}

export interface ExcludedHedgeFund {
  cik: string;
  fund: string;
  manager: string;
  denomination: string;
  ciks: string;
  url: string;
}

export async function getExcludedHedgeFunds(): Promise<ExcludedHedgeFund[]> {
  return cachedFetch("excluded_hedge_funds", async () => {
    const raw = await fetchCSV<RawHedgeFund & { URL: string }>("/database/excluded_hedge_funds.csv");
    return raw.map((r) => ({
      cik: r.CIK,
      fund: r.Fund,
      manager: r.Manager,
      denomination: r.Denomination,
      ciks: r.CIKs,
      url: r.URL || "",
    }));
  });
}

/**
 * Generates a hedge_funds CSV string from an array of funds.
 */
export function generateHedgeFundsCSV(allFunds: HedgeFund[]): string {
  return (
    '"CIK","Fund","Manager","Denomination","CIKs"\n' +
    allFunds
      .map((f) => `"${f.cik}","${f.fund}","${f.manager}","${f.denomination}","${f.ciks}"`)
      .join("\n") + "\n"
  );
}

/**
 * Generates an excluded_hedge_funds CSV string from an array of excluded funds.
 */
export function generateExcludedFundsCSV(allExcluded: ExcludedHedgeFund[]): string {
  return (
    '"CIK","Fund","Manager","Denomination","CIKs","URL"\n' +
    allExcluded
      .map((f) => `"${f.cik}","${f.fund}","${f.manager}","${f.denomination}","${f.ciks}","${f.url}"`)
      .join("\n") + "\n"
  );
}

/**
 * Generates updated hedge_funds CSV after adding a new fund.
 */
export function generateAddFundCSV(
  allFunds: HedgeFund[],
  newFund: HedgeFund
): string {
  return generateHedgeFundsCSV([...allFunds, newFund]);
}

/**
 * Generates updated CSV contents after deleting a fund from hedge_funds
 * and adding it to excluded_hedge_funds. Returns downloadable blobs.
 */
export function generateDeleteFundCSVs(
  allFunds: HedgeFund[],
  excludedFunds: ExcludedHedgeFund[],
  fundToDelete: HedgeFund,
  websiteUrl: string
): { hedgeFundsCSV: string; excludedCSV: string } {
  // Remove from hedge_funds
  const remaining = allFunds.filter((f) => f.cik !== fundToDelete.cik);
  const hedgeFundsCSV =
    '"CIK","Fund","Manager","Denomination","CIKs"\n' +
    remaining
      .map(
        (f) =>
          `"${f.cik}","${f.fund}","${f.manager}","${f.denomination}","${f.ciks}"`
      )
      .join("\n") + "\n";

  // Add to excluded
  const newExcluded: ExcludedHedgeFund = {
    ...fundToDelete,
    url: websiteUrl,
  };
  const allExcluded = [...excludedFunds, newExcluded];
  const excludedCSV =
    '"CIK","Fund","Manager","Denomination","CIKs","URL"\n' +
    allExcluded
      .map(
        (f) =>
          `"${f.cik}","${f.fund}","${f.manager}","${f.denomination}","${f.ciks}","${f.url}"`
      )
      .join("\n") + "\n";

  return { hedgeFundsCSV, excludedCSV };
}

/**
 * Generates updated CSV contents after restoring an excluded fund back to hedge_funds.
 * Removes URL field and moves the fund from excluded to active.
 */
export function generateRestoreFundCSVs(
  allFunds: HedgeFund[],
  excludedFunds: ExcludedHedgeFund[],
  fundToRestore: ExcludedHedgeFund
): { hedgeFundsCSV: string; excludedCSV: string } {
  // Add to hedge_funds (without URL)
  const restored: HedgeFund = {
    cik: fundToRestore.cik,
    fund: fundToRestore.fund,
    manager: fundToRestore.manager,
    denomination: fundToRestore.denomination,
    ciks: fundToRestore.ciks,
  };
  const updatedFunds = [...allFunds, restored];
  const hedgeFundsCSV =
    '"CIK","Fund","Manager","Denomination","CIKs"\n' +
    updatedFunds
      .map(
        (f) =>
          `"${f.cik}","${f.fund}","${f.manager}","${f.denomination}","${f.ciks}"`
      )
      .join("\n") + "\n";

  // Remove from excluded
  const remaining = excludedFunds.filter((f) => f.cik !== fundToRestore.cik);
  const excludedCSV =
    '"CIK","Fund","Manager","Denomination","CIKs","URL"\n' +
    remaining
      .map(
        (f) =>
          `"${f.cik}","${f.fund}","${f.manager}","${f.denomination}","${f.ciks}","${f.url}"`
      )
      .join("\n") + "\n";

  return { hedgeFundsCSV, excludedCSV };
}

export const MODEL_PROVIDERS = ["GitHub", "Groq", "Google", "HuggingFace", "OpenRouter", "Custom"] as const;

/** Display names for CSV client values (used in UI only) */
export const PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  GitHub: "GitHub Models",
  Google: "Google AI Studio",
  Groq: "Groq",
  HuggingFace: "HuggingFace",
  OpenRouter: "OpenRouter",
  Custom: "Custom OpenAI",
};
export type ModelProvider = typeof MODEL_PROVIDERS[number];

export function generateModelsCSV(models: AIModel[]): string {
  return (
    '"ID","Description","Client"\n' +
    models.map((m) => `"${m.id}","${m.description}","${m.client}"`).join("\n") + "\n"
  );
}

export async function saveFileToDisk(content: string, filePath: string): Promise<void> {
  if (IS_GH_PAGES_MODE) {
    // In GitHub Pages mode, download the file instead of saving to server
    downloadFile(content, filePath.split("/").pop() || filePath);
    return;
  }
  const res = await fetch(`${DATABASE_URL}/${filePath}`, {
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
    const raw = await fetchCSV<RawStock>("/database/stocks.csv");
    return raw.map((r) => ({
      cusip: r.CUSIP,
      ticker: r.Ticker,
      company: r.Company,
      sector: r.Sector || undefined,
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

export async function getGICSHierarchy(): Promise<GICSEntry[]> {
  return cachedFetch("gics", async () => {
    const raw = await fetchCSV<RawGICSHierarchy>("/database/GICS/hierarchy.csv");
    return raw.map((r) => ({
      sectorCode: r["Sector Code"],
      sector: r.Sector,
      industryGroupCode: r["Industry Group Code"],
      industryGroup: r["Industry Group"],
      industryCode: r["Industry Code"],
      industry: r.Industry,
      subIndustryCode: r["Sub-Industry Code"],
      subIndustry: r["Sub-Industry"],
    }));
  });
}

/** Available quarters in the repository */
export const AVAILABLE_QUARTERS = ["2025Q1", "2025Q2", "2025Q3", "2025Q4"];

/** Converts a fund name to its filename form (spaces → underscores). */
function fundNameToFileName(name: string): string {
  return name.replace(/ /g, "_");
}

/** Converts a filename form back to fund name (underscores → spaces). */
function fileNameToFundName(name: string): string {
  return name.replace(/_/g, " ");
}

/** Returns only the quarters where a specific fund has data (sorted chronologically). */
export async function getFundAvailableQuarters(fundName: string): Promise<string[]> {
  return cachedFetch(`fund_quarters_${fundName}`, async () => {
    const fileName = fundNameToFileName(fundName);
    const results = await Promise.all(
      AVAILABLE_QUARTERS.map(async (q) => {
        try {
          const fundList = await getQuarterFundList(q);
          return fundList.includes(fileName) ? q : null;
        } catch {
          return null;
        }
      })
    );
    return results.filter((q): q is string => q !== null);
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
    const response = await fetch(`${API_BASE}/api/database/quarters/${quarter}`);
    if (!response.ok) throw new Error(`Failed to list funds for ${quarter}`);
    const files: string[] = await response.json();
    return files;
  });
}

export async function getFundQuarterlyHoldings(
  quarter: string,
  fundName: string
): Promise<QuarterlyHolding[]> {
  const key = `holdings_${quarter}_${fundName}`;
  return cachedFetch(key, async () => {
    const raw = await fetchCSV<RawQuarterlyHolding>(
      `/database/${quarter}/${encodeURIComponent(fundNameToFileName(fundName))}.csv`
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
  fundFilter?: Set<string>
): Promise<StockQuarterAnalysis[]> {
  const cacheKey = fundFilter && fundFilter.size > 0
    ? `quarter_analysis_${quarter}_funds_${[...fundFilter].sort().join(",")}`
    : `quarter_analysis_${quarter}`;
  return cachedFetch(cacheKey, async () => {
    onProgress?.("Fetching fund list…", 5);
    const [allFundNames, stocks] = await Promise.all([getQuarterFundList(quarter), getStocks()]);
    const fundNames = fundFilter && fundFilter.size > 0
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
        })
      );
      results.forEach((r) => allHoldings.push(...r));
      const pct = Math.round(10 + (i / fundNames.length) * 70);
      onProgress?.(`Loaded ${Math.min(i + batchSize, fundNames.length)}/${fundNames.length} funds`, pct);
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
        fth.sharesDeltaPct = (prevShares > 0 && fth.shares > 0)
          ? (fth.deltaShares / prevShares) * 100
          : 0;
      });
    }

    // Step 3: Aggregate to stock level (replicates _aggregate_stock_data)
    const stockMap = new Map<string, StockQuarterAnalysis>();

    for (const fth of fundTickerMap.values()) {
      const existing = stockMap.get(fth.ticker);
      if (existing) {
        existing.totalValue += fth.value;
        existing.totalDeltaValue += fth.deltaValue;
        existing.maxPortfolioPct = Math.max(existing.maxPortfolioPct, fth.portfolioPct);
        (existing as any)._sumPct += fth.portfolioPct;
        (existing as any)._countPct += 1;
        (existing as any)._sumConcentration += fth.fundConcentrationRatio;
        existing.buyerCount += fth.isBuyer ? 1 : 0;
        existing.sellerCount += fth.isSeller ? 1 : 0;
        existing.holderCount += fth.isHolder ? 1 : 0;
        existing.newHolderCount += fth.isNew ? 1 : 0;
        existing.closeCount += fth.isClosed ? 1 : 0;
        existing.highConvictionCount += fth.isHighConviction ? 1 : 0;
        // Accumulation velocity: only buyers who aren't new
        if (fth.isBuyer && !fth.isNew && fth.sharesDeltaPct !== 0) {
          (existing as any)._sumDeltaPct += fth.sharesDeltaPct;
          (existing as any)._countDeltaPct += 1;
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
        } as any);
      }
    }

    // Step 4: Derived metrics (replicates _calculate_derived_metrics)
    const results: StockQuarterAnalysis[] = [];
    for (const s of stockMap.values()) {
      const a = s as any;
      s.avgPortfolioPct = a._countPct > 0 ? a._sumPct / a._countPct : 0;
      s.netBuyers = s.buyerCount - s.sellerCount;
      s.buyerSellerRatio = s.sellerCount > 0 ? s.buyerCount / s.sellerCount : Infinity;
      s.ownershipDeltaAvg = a._countDeltaPct > 0 ? a._sumDeltaPct / a._countDeltaPct : 0;
      s.fundConcentrationAvg = a._countPct > 0 ? a._sumConcentration / a._countPct : 0;

      const previousTotal = s.totalValue - s.totalDeltaValue;
      if (s.newHolderCount === s.holderCount && s.closeCount === 0) {
        s.delta = Infinity;
      } else if (previousTotal !== 0) {
        s.delta = (s.totalDeltaValue / previousTotal) * 100;
      } else {
        s.delta = 0;
      }

      delete a._sumPct;
      delete a._countPct;
      delete a._sumConcentration;
      delete a._sumDeltaPct;
      delete a._countDeltaPct;
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
  onProgress?: (msg: string, pct: number) => void
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
              (h) => h.ticker === ticker && h.cusip !== "Total"
            );
            if (tickerHoldings.length === 0) return null;

            let shares = 0, deltaShares = 0, value = 0, deltaValue = 0, portfolioPct = 0;
            let company = tickerNameMap.get(ticker) || tickerHoldings[0].company;

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
            const sharesDeltaPctVal = (prevShares > 0 && shares > 0)
              ? (deltaShares / prevShares) * 100
              : 0;

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
        })
      );
      batchResults.forEach((r) => { if (r) results.push(r); });
      const pct = Math.round(10 + (i / fundNames.length) * 85);
      onProgress?.(`Scanned ${Math.min(i + batchSize, fundNames.length)}/${fundNames.length} funds`, pct);
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
  onProgress?: (msg: string, pct: number) => void
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
      fth.sharesDeltaPct = (prevShares > 0 && fth.shares > 0) ? (fth.deltaShares / prevShares) * 100 : 0;

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
  quarterShares: number | null;   // shares in latest 13F (null = fund not found)
  deltaShares: number | null;     // nq shares - quarter shares
  deltaType: "NEW" | "INCREASE" | "DECREASE" | "CLOSED" | "NO CHANGE" | "UNKNOWN";
  deltaPct: number | null;        // percentage change vs quarter
  quarterPortfolioPct: number | null;
}

/**
 * Enriches non-quarterly filings with last-quarter data.
 * For each NQ filing, looks up the fund's holdings in the latest available quarter
 * and computes the delta (new position vs quarterly position).
 */
export async function getEnrichedNQFilings(
  onProgress?: (msg: string, pct: number) => void
): Promise<EnrichedNQFiling[]> {
  return cachedFetch("enriched_nq", async () => {
    onProgress?.("Loading filings…", 5);
    const allFilings = await getNonQuarterlyFilings();

    // Deduplicate: keep only the latest filing per Fund+Ticker
    const latestMap = new Map<string, NonQuarterlyFiling>();
    for (const f of allFilings) {
      const key = `${f.fund}||${f.ticker}`;
      const existing = latestMap.get(key);
      if (!existing || f.date > existing.date || (f.date === existing.date && f.filingDate > existing.filingDate)) {
        latestMap.set(key, f);
      }
    }
    const filings = [...latestMap.values()];

    // Find latest available quarter
    onProgress?.("Finding latest quarter…", 10);
    let latestQuarter: string | null = null;
    for (let i = AVAILABLE_QUARTERS.length - 1; i >= 0; i--) {
      try {
        const funds = await getQuarterFundList(AVAILABLE_QUARTERS[i]);
        if (funds.length > 0) {
          latestQuarter = AVAILABLE_QUARTERS[i];
          break;
        }
      } catch {
        continue;
      }
    }

    if (!latestQuarter) {
      // No quarterly data; return filings with unknown delta
      return filings.map((f) => ({
        ...f,
        quarterShares: null,
        deltaShares: null,
        deltaType: "UNKNOWN" as const,
        deltaPct: null,
        quarterPortfolioPct: null,
      }));
    }

    onProgress?.(`Loading ${latestQuarter} data…`, 15);

    // Get unique fund names from filings
    const uniqueFunds = [...new Set(filings.map((f) => f.fund))];

    // Load quarterly holdings for each fund that appears in NQ filings
    // Map: fund → ticker → { shares, portfolioPct } (aggregated across CUSIPs)
    const fundQuarterlyMap = new Map<string, Map<string, { shares: number; portfolioPct: number }>>();
    const batchSize = 10;

    for (let i = 0; i < uniqueFunds.length; i += batchSize) {
      const batch = uniqueFunds.slice(i, i + batchSize);
      const results = await Promise.all(
        batch.map(async (fundName) => {
          try {
            const holdings = await getFundQuarterlyHoldings(latestQuarter!, fundName);
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
        })
      );
      for (const { fundName, tickerMap } of results) {
        fundQuarterlyMap.set(fundName, tickerMap);
      }
      const pct = Math.round(15 + (i / uniqueFunds.length) * 80);
      onProgress?.(`Loaded ${Math.min(i + batchSize, uniqueFunds.length)}/${uniqueFunds.length} funds`, pct);
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
          deltaType: f.shares === 0 ? "CLOSED" as const : "NEW" as const,
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
