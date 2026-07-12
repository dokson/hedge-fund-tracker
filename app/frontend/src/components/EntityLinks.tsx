import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getHedgeFunds } from "@/lib/dataService";
import { CompanyLogo } from "@/components/CompanyLogo";
import { FundLogo } from "@/components/FundLogo";
import { StarButton } from "@/components/StarButton";
import { useStarred } from "@/hooks/useStarred";
import { stockPath, fundPath } from "@/lib/routes";

/** Convert CSV-filename fund name (with underscores) to display name */
// oxlint-disable-next-line react/only-export-components
export function formatFundName(name: string | null | undefined): string {
  if (!name) return "";
  return name.replace(/_/g, " ");
}

/**
 * Hook to resolve a fund filename to its denomination.
 * Returns the denomination if found, otherwise falls back to formatFundName.
 */
// oxlint-disable-next-line react/only-export-components
export function useFundDenomination(fundName: string | null | undefined): string {
  const { data: funds } = useQuery({
    queryKey: ["hedgeFunds"],
    queryFn: getHedgeFunds,
  });
  if (!fundName) return "";
  const fund = funds?.find((f) => f.fund === fundName);
  return fund?.denomination || formatFundName(fundName);
}

/**
 * Renders a company name as a navigable link to its stock page. Use this
 * everywhere the security's display name appears next to its ticker. The
 * styling lives in the .company-link CSS class so the look stays uniform
 * across tables, cards, and headers.
 */
export function CompanyLink({
  ticker,
  company,
  className = "",
  title,
  showStar = false,
}: {
  ticker: string;
  company: string;
  className?: string;
  title?: string;
  /**
   * When true, prepends a star toggle bound to the global "stock" star set.
   * Use in table cells so the star sits visually consistent with the company
   * name across pages instead of floating in a dedicated column.
   */
  showStar?: boolean;
}) {
  const navigate = useNavigate();
  const link = (
    <span
      role="link"
      tabIndex={0}
      title={title ?? company}
      className={`company-link ${className}`}
      onClick={(e) => {
        e.stopPropagation();
        void navigate(stockPath(ticker));
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          e.stopPropagation();
          void navigate(stockPath(ticker));
        }
      }}
    >
      {company}
    </span>
  );
  if (!showStar) return link;
  return (
    <span className="inline-flex items-center gap-2 align-middle">
      <InlineStockStar ticker={ticker} />
      {link}
    </span>
  );
}

function InlineStockStar({ ticker }: { ticker: string }) {
  const { isStarred, toggle } = useStarred("stock");
  return <StarButton active={isStarred(ticker)} onClick={() => toggle(ticker)} size={14} />;
}

export function TickerLink({
  ticker,
  className = "",
  showLogo = true,
}: {
  ticker: string;
  className?: string;
  showLogo?: boolean;
}) {
  const navigate = useNavigate();
  return (
    <span
      role="link"
      tabIndex={0}
      className={`ticker-pill ${className}`}
      onClick={(e) => {
        e.stopPropagation();
        void navigate(stockPath(ticker));
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          e.stopPropagation();
          void navigate(stockPath(ticker));
        }
      }}
    >
      {showLogo && <CompanyLogo ticker={ticker} size={16} />}
      <span>{ticker}</span>
    </span>
  );
}

/**
 * Two-line block: site favicon + fund denomination (bold, navigable) with
 * the manager name muted underneath. Use for table cells where the fund is
 * the primary entity. For inline contexts (lists, paragraphs) prefer FundLink.
 */
export function FundCell({ fundName, className = "" }: { fundName: string; className?: string }) {
  const navigate = useNavigate();
  const { data: funds } = useQuery({ queryKey: ["hedgeFunds"], queryFn: getHedgeFunds });
  const fund = funds?.find((f) => f.fund === fundName);
  // Tables use the short canonical name (CSV `Fund` column) to keep cells
  // narrow. The full legal denomination is preserved in the tooltip.
  const display = formatFundName(fundName);

  return (
    <div className={`flex items-center gap-2.5 min-w-0 ${className}`}>
      <FundLogo fundName={fundName} url={fund?.url} size={16} className="rounded-sm mt-0.5" />
      <div className="flex flex-col min-w-0 leading-tight">
        <span
          role="link"
          tabIndex={0}
          title={fund?.denomination || display}
          className="font-semibold text-foreground hover:text-primary focus-visible:text-primary focus-visible:outline-none transition-colors cursor-pointer truncate"
          onClick={(e) => {
            e.stopPropagation();
            void navigate(fundPath(fundName));
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              e.stopPropagation();
              void navigate(fundPath(fundName));
            }
          }}
        >
          {display}
        </span>
        {fund?.manager && (
          <span className="text-xs text-muted-foreground truncate">{fund.manager}</span>
        )}
      </div>
    </div>
  );
}

export function FundLink({
  fundName,
  displayName,
  className = "",
}: {
  fundName: string;
  displayName?: string;
  className?: string;
}) {
  const navigate = useNavigate();
  const denomination = useFundDenomination(fundName);
  return (
    <span
      role="link"
      tabIndex={0}
      className={`fund-link ${className}`}
      onClick={(e) => {
        e.stopPropagation();
        void navigate(fundPath(fundName));
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          e.stopPropagation();
          void navigate(fundPath(fundName));
        }
      }}
    >
      {displayName || denomination}
    </span>
  );
}
