import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { getHedgeFunds } from "@/lib/dataService";
import { CompanyLogo } from "@/components/CompanyLogo";
import { FundLogo } from "@/components/FundLogo";
import { StarButton } from "@/components/StarButton";
import { useStarred } from "@/hooks/useStarred";
import { stockPath, fundPath } from "@/lib/routes";

/**
 * These are real `<Link>`s, not `role="link"` spans: an anchor with an href is
 * what makes middle-click, cmd-click, "open in new tab" and "copy link
 * address" work, and what puts the target in the status bar.
 *
 * `min-h-6` on each is SC 2.5.8: in stacked table rows the cell links were
 * 17-22px tall, under the 24px minimum, and too close together for the
 * spacing exception to rescue them.
 */

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
  const link = (
    <Link
      to={stockPath(ticker)}
      title={title ?? company}
      className={`company-link min-w-0 min-h-6 ${className}`}
      onClick={(e) => e.stopPropagation()}
    >
      {company}
    </Link>
  );
  if (!showStar) return link;
  return (
    // `min-w-0 max-w-full`: without them this inline-flex is sized by its
    // content, so on a phone the star + company name pushed the whole column
    // past the viewport instead of letting `.company-link` truncate.
    <span className="inline-flex min-w-0 max-w-full items-center gap-2 align-middle">
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
  return (
    <Link
      to={stockPath(ticker)}
      className={`ticker-pill min-h-6 ${className}`}
      onClick={(e) => e.stopPropagation()}
    >
      {showLogo && <CompanyLogo ticker={ticker} size={16} />}
      <span>{ticker}</span>
    </Link>
  );
}

/**
 * Two-line block: site favicon + fund denomination (bold, navigable) with
 * the manager name muted underneath. Use for table cells where the fund is
 * the primary entity. For inline contexts (lists, paragraphs) prefer FundLink.
 */
export function FundCell({ fundName, className = "" }: { fundName: string; className?: string }) {
  const { data: funds } = useQuery({ queryKey: ["hedgeFunds"], queryFn: getHedgeFunds });
  const fund = funds?.find((f) => f.fund === fundName);
  // Tables use the short canonical name (CSV `Fund` column) to keep cells
  // narrow. The full legal denomination is preserved in the tooltip.
  const display = formatFundName(fundName);

  return (
    <div className={`flex items-center gap-2.5 min-w-0 ${className}`}>
      <FundLogo fundName={fundName} url={fund?.url} size={16} className="mt-0.5" />
      <div className="flex flex-col min-w-0 leading-tight">
        <Link
          to={fundPath(fundName)}
          title={fund?.denomination || display}
          className="inline-flex min-h-6 items-center font-semibold text-foreground hover:text-primary-text focus-visible:text-primary-text transition-colors truncate"
          onClick={(e) => e.stopPropagation()}
        >
          {display}
        </Link>
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
  const denomination = useFundDenomination(fundName);
  return (
    <Link
      to={fundPath(fundName)}
      className={`fund-link inline-flex min-h-6 items-center ${className}`}
      onClick={(e) => e.stopPropagation()}
    >
      {displayName || denomination}
    </Link>
  );
}
