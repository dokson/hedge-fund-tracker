import { Star, Users, Building2, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

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
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Star className="h-3.5 w-3.5 text-warning" fill="currentColor" /> Consider starred only:
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
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={() => count > 0 && onClick()}
      disabled={count === 0}
      aria-pressed={active}
      className={active ? "border-primary text-foreground" : "text-muted-foreground"}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
      <Badge variant="secondary" className="h-4 px-1 py-0 text-[11px] leading-none">
        {count}
      </Badge>
    </Button>
  );
}
