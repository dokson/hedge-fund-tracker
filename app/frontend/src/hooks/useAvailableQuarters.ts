import { useQuery } from "@tanstack/react-query";
import { getAvailableQuarters, getLatestQuarter } from "@/lib/dataService";
import type { Quarter } from "@/lib/quarters";

/**
 * Returns the list of available quarter folders and the latest one.
 *
 * The latest quarter comes from a dedicated backend endpoint (single source of truth);
 * the list is fetched separately for UI components that need to enumerate quarters.
 * Both have a short stale time so that newly added quarters appear without a hard refresh.
 */
export function useAvailableQuarters(): {
  quarters: readonly Quarter[];
  latestQuarter: Quarter | undefined;
  isLoading: boolean;
} {
  const { data: quartersData, isLoading: listLoading } = useQuery({
    queryKey: ["availableQuarters"],
    queryFn: getAvailableQuarters,
    staleTime: 60_000,
  });
  const { data: latest, isLoading: latestLoading } = useQuery({
    queryKey: ["latestQuarter"],
    queryFn: getLatestQuarter,
    staleTime: 60_000,
  });
  return {
    quarters: quartersData ?? [],
    latestQuarter: latest ?? undefined,
    isLoading: listLoading || latestLoading,
  };
}
