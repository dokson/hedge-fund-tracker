import type { ElementType } from "react";
import {
  Atom,
  Boxes,
  Briefcase,
  Building2,
  Car,
  Caravan,
  CircuitBoard,
  Clapperboard,
  Code,
  Coins,
  Cpu,
  CreditCard,
  Dices,
  Dna,
  FerrisWheel,
  FlaskConical,
  Flame,
  Fuel,
  Gamepad2,
  Gem,
  GraduationCap,
  Hammer,
  HardHat,
  Hotel,
  Landmark,
  Lock,
  Megaphone,
  Microscope,
  Newspaper,
  Package,
  Pickaxe,
  Pill,
  Plane,
  PlaneTakeoff,
  Plug,
  Recycle,
  Scissors,
  Shirt,
  ShieldCheck,
  Ship,
  ShoppingBag,
  Signal,
  Sofa,
  SprayCan,
  Sprout,
  Stethoscope,
  TrainFront,
  Trees,
  Truck,
  Tv,
  Utensils,
  Wine,
  Wrench,
  Zap,
} from "lucide-react";

// Keyword → glyph, ordered most-specific first. The first rule whose any
// keyword is a substring of the (lower-cased) industry name wins, so multi-word
// combos (e.g. "internet retail", "electronic gaming") must precede the broad
// single-word rules they would otherwise be swallowed by. Rules are also tuned
// so industries within one sector resolve to distinct glyphs where a sensible
// distinct icon exists.
const RULES: ReadonlyArray<{ kw: readonly string[]; icon: ElementType }> = [
  { kw: ["gaming", "multimedia"], icon: Gamepad2 },
  // Technology
  { kw: ["semiconductor"], icon: CircuitBoard },
  { kw: ["software", "internet content", "it services", "information"], icon: Code },
  { kw: ["computer", "electronic", "hardware", "technology"], icon: Cpu },
  // Healthcare
  { kw: ["biotech"], icon: Dna },
  { kw: ["drug", "pharma"], icon: Pill },
  { kw: ["diagnostic", "laboratory", "life sciences"], icon: Microscope },
  { kw: ["medical", "health", "hospital", "care", "device", "instrument"], icon: Stethoscope },
  // Financials
  { kw: ["bank"], icon: Landmark },
  { kw: ["insurance"], icon: ShieldCheck },
  { kw: ["payment", "credit services"], icon: CreditCard },
  { kw: ["capital", "asset management", "financial", "credit", "mortgage"], icon: Coins },
  // Consumer — specific combos before broad ones
  { kw: ["recreational vehicle"], icon: Caravan },
  { kw: ["internet retail", "e-commerce", "online retail"], icon: ShoppingBag },
  { kw: ["home improvement"], icon: Hammer },
  { kw: ["personal service"], icon: Scissors },
  { kw: ["gambling", "casino"], icon: Dices },
  { kw: ["leisure"], icon: FerrisWheel },
  { kw: ["hotel", "lodging", "resort", "travel"], icon: Hotel },
  { kw: ["restaurant", "food", "packaged", "grocer", "confection"], icon: Utensils },
  { kw: ["beverage", "brewer", "winer", "distiller", "tobacco"], icon: Wine },
  { kw: ["apparel", "footwear", "luxury", "textile"], icon: Shirt },
  { kw: ["furnish", "furniture"], icon: Sofa },
  { kw: ["household", "personal product", "cosmetic"], icon: SprayCan },
  { kw: ["retail", "store", "merchandis", "department"], icon: ShoppingBag },
  // Energy & Materials
  { kw: ["oil", "gas", "petroleum", "drilling", "refining", "midstream"], icon: Fuel },
  { kw: ["coal"], icon: Flame },
  { kw: ["uranium", "nuclear"], icon: Atom },
  { kw: ["gold", "silver", "precious"], icon: Gem },
  { kw: ["copper", "aluminum", "steel", "metal", "mining"], icon: Pickaxe },
  { kw: ["chemical"], icon: FlaskConical },
  { kw: ["lumber", "wood", "paper", "forest"], icon: Trees },
  { kw: ["agric", "farm", "fertilizer"], icon: Sprout },
  { kw: ["building material", "construction", "cement"], icon: HardHat },
  // Industrials & Transport
  { kw: ["airline"], icon: PlaneTakeoff },
  { kw: ["aerospace", "defense", "aircraft"], icon: Plane },
  { kw: ["marine", "shipping"], icon: Ship },
  { kw: ["rail"], icon: TrainFront },
  { kw: ["truck", "freight", "logistics", "delivery"], icon: Truck },
  { kw: ["auto", "vehicle"], icon: Car },
  { kw: ["machinery", "tools", "engineering", "manufactur", "industrial"], icon: Wrench },
  { kw: ["electrical", "power"], icon: Plug },
  { kw: ["packaging", "container"], icon: Package },
  { kw: ["waste", "environmental", "recycling", "pollution"], icon: Recycle },
  { kw: ["utilit", "water"], icon: Zap },
  { kw: ["reit", "real estate"], icon: Building2 },
  // Communication — distinct glyphs per industry
  { kw: ["broadcast"], icon: Tv },
  { kw: ["publishing", "newspaper", "publication"], icon: Newspaper },
  { kw: ["entertainment", "media", "movie", "studio", "music"], icon: Clapperboard },
  { kw: ["telecom", "wireless", "communication"], icon: Signal },
  { kw: ["advertising", "marketing"], icon: Megaphone },
  // Other services
  { kw: ["education"], icon: GraduationCap },
  { kw: ["staffing", "employment", "consulting", "business"], icon: Briefcase },
  { kw: ["security", "protection"], icon: Lock },
  { kw: ["conglomerate", "diversified"], icon: Boxes },
];

/**
 * Best-effort glyph for a Yahoo Finance industry name. Returns null when no
 * rule matches, so callers can fall back to the parent sector's icon.
 */
export function getIndustryIcon(industry: string): ElementType | null {
  const name = industry.toLowerCase();
  for (const { kw, icon } of RULES) {
    if (kw.some((k) => name.includes(k))) return icon;
  }
  return null;
}
