import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getHedgeFunds } from "@/lib/dataService";

/** Convert CSV-filename fund name (with underscores) to display name */
export function formatFundName(name: string): string {
  return name.replace(/_/g, " ");
}

/**
 * Hook to resolve a fund filename to its denomination.
 * Returns the denomination if found, otherwise falls back to formatFundName.
 */
export function useFundDenomination(fundName: string): string {
  const { data: funds } = useQuery({
    queryKey: ["hedgeFunds"],
    queryFn: getHedgeFunds,
  });
  const fund = funds?.find((f) => f.fund === fundName);
  return fund?.denomination || formatFundName(fundName);
}

export function TickerLink({ ticker, className = "" }: { ticker: string; className?: string }) {
  const navigate = useNavigate();
  return (
    <span
      className={`ticker-link ${className}`}
      onClick={(e) => { e.stopPropagation(); navigate(`/stock/${ticker}`); }}
    >
      {ticker}
    </span>
  );
}

export function FundLink({ fundName, displayName, className = "" }: { fundName: string; displayName?: string; className?: string }) {
  const navigate = useNavigate();
  const denomination = useFundDenomination(fundName);
  return (
    <span
      className={`fund-link ${className}`}
      onClick={(e) => { e.stopPropagation(); navigate(`/funds/${encodeURIComponent(fundName)}`); }}
    >
      {displayName || denomination}
    </span>
  );
}
