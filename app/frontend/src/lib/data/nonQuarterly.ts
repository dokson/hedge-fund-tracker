/**
 * Non-quarterly filings (13D/G + Form 4) and their enrichment against each
 * fund's own latest 13F snapshot.
 */

import { cachedFetch, fetchCSV } from "./fetch";
import { parseValueString } from "./format";
import { getFundAvailableQuarters, getFundQuarterlyHoldings } from "./quarterData";
import type {
  EnrichedNQFiling,
  FundQuarterSnapshot,
  NonQuarterlyFiling,
  RawNonQuarterly,
} from "./types";

export async function getNonQuarterlyFilings(): Promise<NonQuarterlyFiling[]> {
  return cachedFetch("non_quarterly", async () => {
    const raw = await fetchCSV<RawNonQuarterly>("/database/non_quarterly.csv", [
      "Fund",
      "CUSIP",
      "Ticker",
      "Company",
      "Shares",
      "Value",
      "Avg_Price",
      "Date",
      "Filing_Date",
    ] satisfies readonly (keyof RawNonQuarterly)[]);
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

/**
 * Computes the delta of one non-quarterly filing against the fund's latest 13F
 * snapshot. NEW positions get an estimated portfolio weight over the merged
 * total (mirrors the backend, which recomputes weights after the merge).
 */
export function enrichNQFiling(
  f: NonQuarterlyFiling,
  fundData: FundQuarterSnapshot | undefined,
): EnrichedNQFiling {
  if (!fundData) {
    return {
      ...f,
      quarterShares: 0,
      deltaShares: f.shares,
      deltaType: f.shares === 0 ? "CLOSED" : "NEW",
      deltaPct: null,
      quarterPortfolioPct: null,
      estimatedPortfolioPct: null,
    };
  }

  const qHolding = fundData.tickerMap.get(f.ticker);
  const qShares = qHolding ? qHolding.shares : 0;
  const qPct = qHolding ? qHolding.portfolioPct : null;
  const delta = f.shares - qShares;

  let deltaType: EnrichedNQFiling["deltaType"];
  if (f.shares === 0) {
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

  let estimatedPortfolioPct: number | null = null;
  if (deltaType === "NEW" && fundData.totalValue > 0) {
    const valueNum = parseValueString(f.value);
    estimatedPortfolioPct = (valueNum / (fundData.totalValue + valueNum)) * 100;
  }

  return {
    ...f,
    quarterShares: qShares,
    deltaShares: delta,
    deltaType,
    deltaPct: qShares > 0 ? (delta / qShares) * 100 : null,
    quarterPortfolioPct: qPct,
    estimatedPortfolioPct,
  };
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
    const emptySnapshot = (): FundQuarterSnapshot => ({
      tickerMap: new Map(),
      totalValue: 0,
    });
    const fundQuarterlyMap = new Map<string, FundQuarterSnapshot>();
    const batchSize = 10;

    for (let i = 0; i < uniqueFunds.length; i += batchSize) {
      const batch = uniqueFunds.slice(i, i + batchSize);
      const results = await Promise.all(
        batch.map(async (fundName) => {
          try {
            const fundQuarters = await getFundAvailableQuarters(fundName);
            const fundLatest = fundQuarters[fundQuarters.length - 1];
            if (!fundLatest) {
              return { fundName, snapshot: emptySnapshot() };
            }
            const holdings = await getFundQuarterlyHoldings(fundLatest, fundName);
            const snapshot = emptySnapshot();
            for (const h of holdings) {
              if (h.cusip === "Total") {
                snapshot.totalValue = parseValueString(h.value);
              } else if (h.ticker) {
                const existing = snapshot.tickerMap.get(h.ticker);
                if (existing) {
                  existing.shares += h.shares;
                  existing.portfolioPct += h.portfolioPct;
                } else {
                  snapshot.tickerMap.set(h.ticker, {
                    shares: h.shares,
                    portfolioPct: h.portfolioPct,
                  });
                }
              }
            }
            return { fundName, snapshot };
          } catch {
            return { fundName, snapshot: emptySnapshot() };
          }
        }),
      );
      for (const { fundName, snapshot } of results) {
        fundQuarterlyMap.set(fundName, snapshot);
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
      const entry = enrichNQFiling(f, fundQuarterlyMap.get(f.fund));
      if (entry.deltaType !== "NO CHANGE") {
        enriched.push(entry);
      }
    }

    onProgress?.("Done", 100);
    return enriched;
  });
}
