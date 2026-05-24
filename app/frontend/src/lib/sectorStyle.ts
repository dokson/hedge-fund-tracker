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

export interface SectorStyle {
  icon: React.ElementType;
  /** Tailwind text-color class for foreground (icon + label). */
  color: string;
  /** Tailwind bg-color class for filled chips. */
  bg: string;
  /** Tailwind border-color class. */
  border: string;
  /** Tailwind bg-color class for the small dot used in outline chips. */
  dot: string;
}

export const SECTOR_STYLE: Record<string, SectorStyle> = {
  Technology: {
    icon: Cpu,
    color: "text-blue-400",
    bg: "bg-blue-950/40",
    border: "border-blue-700",
    dot: "bg-blue-400",
  },
  "Financial Services": {
    icon: BarChart3,
    color: "text-emerald-400",
    bg: "bg-emerald-950/40",
    border: "border-emerald-700",
    dot: "bg-emerald-400",
  },
  Healthcare: {
    icon: Heart,
    color: "text-pink-400",
    bg: "bg-pink-950/40",
    border: "border-pink-700",
    dot: "bg-pink-400",
  },
  "Consumer Cyclical": {
    icon: ShoppingCart,
    color: "text-yellow-400",
    bg: "bg-yellow-950/40",
    border: "border-yellow-700",
    dot: "bg-yellow-400",
  },
  "Consumer Defensive": {
    icon: Apple,
    color: "text-orange-400",
    bg: "bg-orange-950/40",
    border: "border-orange-700",
    dot: "bg-orange-400",
  },
  "Communication Services": {
    icon: Radio,
    color: "text-purple-400",
    bg: "bg-purple-950/40",
    border: "border-purple-700",
    dot: "bg-purple-400",
  },
  Industrials: {
    icon: Factory,
    color: "text-sky-400",
    bg: "bg-sky-950/40",
    border: "border-sky-700",
    dot: "bg-sky-400",
  },
  Energy: {
    icon: Zap,
    color: "text-amber-400",
    bg: "bg-amber-950/40",
    border: "border-amber-700",
    dot: "bg-amber-400",
  },
  Utilities: {
    icon: Plug,
    color: "text-teal-400",
    bg: "bg-teal-950/40",
    border: "border-teal-700",
    dot: "bg-teal-400",
  },
  "Real Estate": {
    icon: Building2,
    color: "text-indigo-400",
    bg: "bg-indigo-950/40",
    border: "border-indigo-700",
    dot: "bg-indigo-400",
  },
  "Basic Materials": {
    icon: Mountain,
    color: "text-slate-400",
    bg: "bg-slate-900/60",
    border: "border-slate-600",
    dot: "bg-slate-400",
  },
  ETF: {
    icon: Layers,
    color: "text-zinc-300",
    bg: "bg-zinc-900/60",
    border: "border-zinc-600",
    dot: "bg-zinc-300",
  },
};

export const DEFAULT_SECTOR_STYLE: SectorStyle = {
  icon: Layers,
  color: "text-muted-foreground",
  bg: "bg-muted/40",
  border: "border-border",
  dot: "bg-muted-foreground",
};

export function getSectorStyle(sector: string | undefined | null): SectorStyle {
  if (!sector) return DEFAULT_SECTOR_STYLE;
  return SECTOR_STYLE[sector] ?? DEFAULT_SECTOR_STYLE;
}
