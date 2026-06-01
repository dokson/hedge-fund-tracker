import { Star, Users, Building2, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";

/**
 * "Consider Starred only" filter row — two toggle chips (Funds / Stocks) bound
 * to the global star sets. Shared by Latest Filings and Quarterly Trends so the
 * markup and behaviour stay in one place. Renders nothing when nothing is
 * starred, so callers don't need their own guard.
 */
export function StarredFilterToggle({
  fundsCount,
  stocksCount,
  filterFunds,
  filterStocks,
  onToggleFunds,
  onToggleStocks,
  className = "",
}: {
  fundsCount: number;
  stocksCount: number;
  filterFunds: boolean;
  filterStocks: boolean;
  onToggleFunds: () => void;
  onToggleStocks: () => void;
  className?: string;
}) {
  if (fundsCount === 0 && stocksCount === 0) return null;
  return (
    <div className={`flex flex-wrap items-center gap-3 ${className}`}>
      <span className="text-xs text-muted-foreground flex items-center gap-1">
        <Star className="h-3 w-3" fill="currentColor" /> Consider Starred only:
      </span>
      <ToggleChip
        icon={Users}
        label="Funds"
        count={fundsCount}
        active={filterFunds}
        onClick={onToggleFunds}
      />
      <ToggleChip
        icon={Building2}
        label="Stocks"
        count={stocksCount}
        active={filterStocks}
        onClick={onToggleStocks}
      />
    </div>
  );
}

function ToggleChip({
  icon: Icon,
  label,
  count,
  active,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={() => count > 0 && onClick()}
      disabled={count === 0}
      aria-pressed={active}
      className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md border transition-colors ${
        active
          ? "bg-primary text-primary-foreground border-primary"
          : "bg-card border-border text-muted-foreground hover:text-foreground hover:border-foreground/30"
      } disabled:opacity-40 disabled:cursor-not-allowed`}
    >
      <Icon className="h-3 w-3" /> {label}
      <Badge variant="secondary" className="text-[9px] px-1.5 py-0 h-4 leading-none">
        {count}
      </Badge>
    </button>
  );
}
