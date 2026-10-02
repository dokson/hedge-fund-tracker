import { useQuery } from "@tanstack/react-query";
import { clearCache, getEnrichedNQFilings } from "@/lib/dataService";

/**
 * The non-quarterly filings enriched against each fund's latest 13F. Every page
 * reads them through this hook so the query key always maps to one loader.
 */
export function useEnrichedNQFilings() {
  return useQuery({
    queryKey: ["enrichedNQFilings"],
    queryFn: () => {
      // Drop both layers, or the enrichment would rebuild from stale raw filings.
      clearCache("non_quarterly");
      clearCache("enriched_nq");
      return getEnrichedNQFilings();
    },
  });
}
