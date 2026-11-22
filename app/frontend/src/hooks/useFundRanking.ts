import { useQuery } from "@tanstack/react-query";

import { getFundPerformanceRows } from "@/lib/dataService";
import { rankFunds } from "@/lib/fundRanking";

/**
 * The fund ranking over fund_performance.csv, one cache entry for every page that shows a
 * fund's standing or return per year (ranking, fund page, stock page, landing).
 */
export function useFundRanking() {
  return useQuery({
    queryKey: ["fundRanking"],
    queryFn: async () => rankFunds(await getFundPerformanceRows()),
    staleTime: 10 * 60 * 1000,
  });
}

/** Each fund's return per year by name; empty while the ranking loads. */
export function useAnnualReturns(): Map<string, number | null> {
  const { data } = useFundRanking();
  return new Map((data?.funds ?? []).map((f) => [f.fund, f.annualReturn]));
}
