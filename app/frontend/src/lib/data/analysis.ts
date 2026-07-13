/**
 * Client-side analysis pipeline: quarter-level consensus (mirroring the Python
 * quarter_analysis), per-stock fund holdings, and per-fund portfolios.
 */

import { IS_GH_PAGES_MODE } from "../config";
import { withSmartScores } from "../smartScore";
import { cachedFetch } from "./fetch";
import { formatPct, parseValueString } from "./format";
import { fileNameToFundName } from "./funds";
import { getEnrichedNQFilings } from "./nonQuarterly";
import { getAvailableQuarters, getFundQuarterlyHoldings, getQuarterFundList } from "./quarterData";
import { getStocks } from "./stocks";
import type {
  EnrichedNQFiling,
  FundTickerHolding,
  QuarterlyHolding,
  StockQuarterAnalysis,
} from "./types";

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
  const body: unknown = await response.json();
  if (!Array.isArray(body)) throw new Error("Malformed quarter analysis: expected an array");
  const raw = body as RawAnalysisRow[];
  // JSON has no ±Infinity: the backend serializer nulls it out. An all-new
  // stock's delta IS Infinity (same rule as aggregateStockLevel) — rebuild it
  // instead of flattening to 0%, which would mislabel NEW positions.
  const rebuildDelta = (r: RawAnalysisRow): number => {
    if (r.Delta != null) return r.Delta;
    const allNew =
      (r.New_Holder_Count ?? 0) === (r.Holder_Count ?? 0) && (r.Close_Count ?? 0) === 0;
    return allNew ? Infinity : 0;
  };
  return withSmartScores(
    raw.map((r) => ({
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
      delta: rebuildDelta(r),
    })),
  );
}

/**
 * Aggregates per-(fund, ticker) holdings to the stock level.
 *
 * Mirrors the Python chain `_calculate_fund_level_flags` →
 * `_aggregate_stock_data` → `_calculate_derived_metrics` exactly. The two
 * implementations are kept in lockstep by a shared golden fixture
 * (tests/fixtures/analysis_golden.json) asserted from both sides; changing
 * one without the other fails CI. Input holdings must already carry
 * portfolioPctRank, fundConcentrationRatio and sharesDeltaPct (assigned
 * per-fund upstream); the activity flags are derived here.
 */
export function aggregateStockLevel(holdings: FundTickerHolding[]): StockQuarterAnalysis[] {
  const flagged = holdings.map((h) => {
    const isNew = h.shares > 0 && h.shares === h.deltaShares;
    return {
      ...h,
      isBuyer: h.deltaValue > 0,
      isSeller: h.deltaValue < 0,
      isHolder: h.shares > 0,
      isNew,
      isClosed: h.shares === 0,
      isHighConviction: isNew && (h.portfolioPctRank <= 10 || h.portfolioPct > 3.0),
    };
  });

  interface StockQuarterAccumulator extends StockQuarterAnalysis {
    _sumPct: number;
    _countPct: number;
    _sumConcentration: number;
    _sumDeltaPct: number;
    _countDeltaPct: number;
  }
  const stockMap = new Map<string, StockQuarterAccumulator>();

  for (const fth of flagged) {
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
        company: fth.company,
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

  const results: StockQuarterAnalysis[] = [];
  for (const acc of stockMap.values()) {
    const { _sumPct, _countPct, _sumConcentration, _sumDeltaPct, _countDeltaPct, ...s } = acc;
    s.avgPortfolioPct = _countPct ? _sumPct / _countPct : 0;
    s.netBuyers = s.buyerCount - s.sellerCount;
    s.buyerSellerRatio = s.sellerCount > 0 ? s.buyerCount / s.sellerCount : Infinity;
    s.ownershipDeltaAvg = _countDeltaPct ? _sumDeltaPct / _countDeltaPct : 0;
    s.fundConcentrationAvg = _countPct ? _sumConcentration / _countPct : 0;

    const previousTotal = s.totalValue - s.totalDeltaValue;
    if (s.newHolderCount === s.holderCount && s.closeCount === 0) {
      s.delta = Infinity;
    } else if (previousTotal !== 0) {
      s.delta = (s.totalDeltaValue / previousTotal) * 100;
    } else {
      s.delta = 0;
    }

    results.push(s);
  }
  return results;
}

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
        fth.portfolioPctRank = idx + 1;
        fth.fundConcentrationRatio = top10Sum;

        // Shares delta pct (velocity of accumulation, only for existing positions)
        const prevShares = fth.shares - fth.deltaShares;
        fth.sharesDeltaPct =
          prevShares > 0 && fth.shares > 0 ? (fth.deltaShares / prevShares) * 100 : 0;
      });
    }

    // Steps 3 & 4: fund flags + stock-level aggregation + derived metrics,
    // then the on-the-fly smart score (kept OUT of the golden-pinned
    // aggregateStockLevel so the Python/TS equivalence fixture is untouched).
    const results = withSmartScores(aggregateStockLevel([...fundTickerMap.values()]));

    onProgress?.("Done", 100);
    return results;
  });
}

/**
 * Overlays recent non-quarterly filings (13D/G, Form 4) onto the 13F holdings
 * of one ticker — the client-side mirror of the backend's latest-quarter merge.
 * Fresher share counts replace stale 13F rows, zero-share filings close them,
 * and funds appearing only via a non-quarterly filing gain a NEW row.
 */
export function mergeNonQuarterlyHoldings(
  holdings: FundTickerHolding[],
  nqFilings: EnrichedNQFiling[],
): FundTickerHolding[] {
  const merged = new Map(holdings.map((h) => [h.fund, { ...h }]));

  for (const filing of nqFilings) {
    const existing = merged.get(filing.fund);

    if (existing && existing.shares > 0) {
      // The fund filed a 13F this quarter: recompute the delta against it.
      if (filing.shares === 0) {
        merged.set(filing.fund, {
          ...existing,
          shares: 0,
          deltaShares: -existing.shares,
          value: 0,
          deltaValue: -existing.value,
          delta: "CLOSE",
          isBuyer: false,
          isSeller: true,
          isHolder: false,
          isNew: false,
          isClosed: true,
        });
        continue;
      }
      const value = parseValueString(filing.value);
      const deltaShares = filing.shares - existing.shares;
      const deltaPct = (deltaShares / existing.shares) * 100;
      merged.set(filing.fund, {
        ...existing,
        shares: filing.shares,
        deltaShares,
        value,
        // Filing-price basis: subtracting the quarter-end 13F value would
        // count pure price drift as traded value and flip the buy/sell sign.
        deltaValue: (value * deltaShares) / filing.shares,
        sharesDeltaPct: deltaPct,
        delta: formatPct(deltaPct, true),
        isBuyer: deltaShares > 0,
        isSeller: deltaShares < 0,
        isHolder: true,
        isNew: false,
        isClosed: false,
      });
      continue;
    }

    // No 13F row this quarter: the enrichment already computed the delta
    // against the fund's OWN latest filed quarter — trust it (a fund that has
    // not filed yet is not opening a NEW position when it tops up an old one).
    const held = filing.quarterShares !== null && filing.quarterShares > 0;
    if (filing.shares === 0 && !held) continue;

    const value = parseValueString(filing.value);
    const isNew = !held;
    const isClosed = filing.shares === 0;
    const deltaShares = filing.deltaShares ?? filing.shares;
    const deltaValue = isNew || filing.shares === 0 ? value : (value * deltaShares) / filing.shares;
    merged.set(filing.fund, {
      fund: filing.fund,
      ticker: filing.ticker,
      company: filing.company,
      shares: filing.shares,
      deltaShares,
      value,
      deltaValue,
      portfolioPct: filing.quarterPortfolioPct ?? filing.estimatedPortfolioPct ?? 0,
      portfolioPctRank: 0,
      sharesDeltaPct: filing.deltaPct ?? (isNew ? 100 : 0),
      fundConcentrationRatio: 0,
      delta: isClosed
        ? "CLOSE"
        : isNew
          ? "NEW"
          : filing.deltaPct !== null
            ? formatPct(filing.deltaPct, true)
            : "NO CHANGE",
      isBuyer: !isClosed && deltaShares > 0,
      isSeller: isClosed || deltaShares < 0,
      isHolder: !isClosed,
      isNew,
      isClosed,
      isHighConviction: false,
    });
  }

  return [...merged.values()];
}

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
        batch.map(async (fileName): Promise<FundTickerHolding | null> => {
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
            };
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

    // The latest quarter's view overlays fresher 13D/G + Form 4 activity, so a
    // stock bought after the last 13F round still shows its holders (mirrors
    // the backend's latest-quarter merge).
    const quarters = await getAvailableQuarters();
    if (quarter === quarters.at(-1)) {
      onProgress?.("Merging non-quarterly filings…", 96);
      const nqFilings = (await getEnrichedNQFilings()).filter((f) => f.ticker === ticker);
      const merged = mergeNonQuarterlyHoldings(results, nqFilings);
      onProgress?.("Done", 100);
      return merged.sort((a, b) => b.shares - a.shares);
    }

    onProgress?.("Done", 100);
    return results.sort((a, b) => b.shares - a.shares);
  });
}

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
