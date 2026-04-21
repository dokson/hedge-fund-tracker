import { useQuery } from "@tanstack/react-query";
import { getAvailableQuarters } from "@/lib/dataService";
import type { Quarter } from "@/lib/quarters";

/**
 * Returns the list of available quarter folders and the latest one.
 * Cached indefinitely (changes require a new backend fetch / page reload).
 */
export function useAvailableQuarters(): {
  quarters: readonly Quarter[];
  latestQuarter: Quarter | undefined;
  isLoading: boolean;
} {
  const { data, isLoading } = useQuery({
    queryKey: ["availableQuarters"],
    queryFn: getAvailableQuarters,
    staleTime: Infinity,
  });
  const quarters = data ?? [];
  return {
    quarters,
    latestQuarter: quarters.at(-1),
    isLoading,
  };
}
