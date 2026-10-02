import { skipToken, useQuery } from "@tanstack/react-query";
import { fetchQuarterAnalysis, runQuarterAnalysis } from "@/lib/dataService";
import type { StockQuarterAnalysis } from "@/lib/dataService";

type ProgressFn = (msg: string, pct: number) => void;

interface QuarterAnalysisOptions {
  onProgress?: ProgressFn;
  /** Restrict the analysis to these funds (client-side pipeline, own cache key). */
  fundFilter?: ReadonlySet<string>;
}

/** The single query key for a quarter's stock-level analysis. */
export function quarterAnalysisKey(
  quarter: string | undefined,
  fundFilter?: ReadonlySet<string>,
): readonly unknown[] {
  return fundFilter && fundFilter.size > 0
    ? ["quarterAnalysis", quarter, [...fundFilter].sort().join(",")]
    : ["quarterAnalysis", quarter];
}

/**
 * A quarter's stock-level analysis: the backend frame first, the client-side
 * pipeline as fallback. Every page reads it through this hook so one query key
 * always maps to one loader and the smart score agrees everywhere.
 */
export function useQuarterAnalysis(
  quarter: string | undefined,
  { onProgress, fundFilter }: QuarterAnalysisOptions = {},
) {
  const filtered = fundFilter && fundFilter.size > 0 ? new Set(fundFilter) : undefined;
  return useQuery<readonly StockQuarterAnalysis[]>({
    queryKey: quarterAnalysisKey(quarter, filtered),
    queryFn: quarter
      ? async () => {
          if (filtered) return runQuarterAnalysis(quarter, onProgress, filtered);
          return (
            (await fetchQuarterAnalysis(quarter)) ?? (await runQuarterAnalysis(quarter, onProgress))
          );
        }
      : skipToken,
    staleTime: 10 * 60 * 1000,
  });
}
