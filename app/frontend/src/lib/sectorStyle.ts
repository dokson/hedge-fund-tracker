import type { CSSProperties } from "react";
import {
  Apple,
  BarChart3,
  Building2,
  Cpu,
  Factory,
  Heart,
  Layers,
  Mountain,
  Plug,
  Radio,
  ShoppingCart,
  Zap,
} from "lucide-react";

/**
 * Sector colours are theme tokens, so both themes keep AA on their own
 * surfaces. Every real sector carries a hue; the neutral is reserved for a
 * sector the registry does not know. Consecutive registry entries never share
 * a token, so neighbouring rows in a sector list stay distinguishable.
 */
export type SectorToken =
  | "chart-1"
  | "chart-2"
  | "chart-3"
  | "chart-4"
  | "chart-5"
  | "chart-6"
  | "chart-7"
  | "muted-foreground";

export interface SectorStyle {
  icon: React.ElementType;
  /** The bare CSS variable name, e.g. "chart-1". */
  token: SectorToken;
  /** The resolved colour, ready for an inline style. */
  cssVar: string;
}

/** Shape of the sector tag: the neutral chip, sentence case, no border. */
export const SECTOR_PILL = "chip sector-pill gap-1";

/**
 * The hue goes inline, never in a class: a class built from the token would be
 * assembled at runtime and Tailwind's scanner would never emit it. It reaches
 * the icon alone through `--sector-hue`; the label reads on the neutral chip,
 * because a hue over a 15% wash of itself cannot reach 4.5:1.
 */
export function sectorPillStyle(style: SectorStyle): CSSProperties {
  return { "--sector-hue": style.cssVar } as CSSProperties;
}

function fromToken(icon: React.ElementType, token: SectorToken): SectorStyle {
  return { icon, token, cssVar: `hsl(var(--${token}))` };
}

export const SECTOR_STYLE: Record<string, SectorStyle> = {
  Technology: fromToken(Cpu, "chart-1"),
  "Financial Services": fromToken(BarChart3, "chart-2"),
  Healthcare: fromToken(Heart, "chart-3"),
  "Consumer Cyclical": fromToken(ShoppingCart, "chart-4"),
  "Consumer Defensive": fromToken(Apple, "chart-5"),
  "Communication Services": fromToken(Radio, "chart-1"),
  Industrials: fromToken(Factory, "chart-6"),
  Energy: fromToken(Zap, "chart-4"),
  Utilities: fromToken(Plug, "chart-2"),
  "Real Estate": fromToken(Building2, "chart-5"),
  "Basic Materials": fromToken(Mountain, "chart-3"),
  ETF: fromToken(Layers, "chart-7"),
};

export const DEFAULT_SECTOR_STYLE: SectorStyle = fromToken(Layers, "muted-foreground");

export function getSectorStyle(sector: string | undefined | null): SectorStyle {
  if (!sector) return DEFAULT_SECTOR_STYLE;
  return SECTOR_STYLE[sector] ?? DEFAULT_SECTOR_STYLE;
}
