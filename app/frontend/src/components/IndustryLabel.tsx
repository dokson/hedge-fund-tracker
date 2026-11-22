import { getSectorStyle, SECTOR_PILL, sectorPillStyle } from "@/lib/sectorStyle";
import { cn } from "@/lib/utils";

/**
 * A stock's industry in a table or card, as the sector pill the stock page header uses: the
 * sector's icon in its hue, the industry name (or the sector when the industry is unknown)
 * on the neutral chip, truncated with the full name on hover. A dash when neither is known.
 */
export function IndustryLabel({
  sector,
  industry,
  className,
}: {
  sector?: string;
  industry?: string;
  className?: string;
}) {
  const label = industry ?? sector;
  if (!label) return <span className="text-xs text-muted-foreground">—</span>;
  const style = getSectorStyle(sector);
  const Icon = style.icon;
  return (
    <span
      className={cn(SECTOR_PILL, "max-w-full", className)}
      style={sectorPillStyle(style)}
      title={sector && industry ? `${industry} (${sector})` : label}
    >
      <Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
      <span className="truncate">{label}</span>
    </span>
  );
}
