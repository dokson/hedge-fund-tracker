import {
  BarChart3,
  BookOpen,
  CandlestickChart,
  ClipboardCheck,
  Cpu,
  Database,
  FileText,
  LineChart,
  Settings2,
  Sparkles,
  Wallet,
  type LucideIcon,
} from "lucide-react";

import { IS_GH_PAGES_MODE } from "@/lib/config";
import { ROUTES } from "@/lib/routes";

export interface MenuDoor {
  title: string;
  /** Two-letter code shown when the rail is collapsed. */
  code: string;
  /** Drawn in the row and, alone, on the collapsed rail. */
  icon: LucideIcon;
  url: string;
  /** AI doors carry the magenta tone; local doors need the Python backend. */
  tone?: "ai" | "local";
  /** One line shown under the door on the landing menu. */
  blurb?: string;
}

export interface MenuSection {
  label: string;
  doors: MenuDoor[];
}

const LOCAL_DOORS: MenuDoor[] = IS_GH_PAGES_MODE
  ? []
  : [
      {
        title: "Funds Configuration",
        code: "FC",
        icon: Settings2,
        url: ROUTES.fundsConfig,
        tone: "local",
      },
      { title: "AI Settings", code: "AS", icon: Cpu, url: ROUTES.aiSettings, tone: "local" },
      {
        title: "Update Operations",
        code: "DB",
        icon: Database,
        url: ROUTES.database,
        tone: "local",
      },
    ];

export const MENU_SECTIONS: readonly MenuSection[] = [
  {
    label: "Board",
    doors: [
      {
        title: "Latest Filings",
        code: "LF",
        icon: FileText,
        url: ROUTES.latest,
        blurb: "13D/G and Form 4 layered on the last 13F, with deltas vs the prior quarter.",
      },
      {
        title: "Quarterly Trends",
        code: "QT",
        icon: BarChart3,
        url: ROUTES.quarterly,
        blurb: "Cross-fund consensus: who is accumulating, the new names, the biggest bets.",
      },
      {
        title: "Strategy Performance",
        code: "SP",
        icon: LineChart,
        url: ROUTES.strategyPerformance,
        blurb: "A descriptive backtest of the consensus screens against the S&P 500.",
      },
      {
        title: "Fund Portfolios",
        code: "FP",
        icon: Wallet,
        url: ROUTES.funds,
        blurb: "Managers selected by track record, and exactly what each one holds.",
      },
      {
        title: "Stocks",
        code: "ST",
        icon: CandlestickChart,
        url: ROUTES.stocks,
        blurb: "For any ticker: who owns it and how conviction is shifting.",
      },
    ],
  },
  {
    label: "AI",
    doors: [
      {
        title: "Most Promising Stocks",
        code: "AI",
        icon: Sparkles,
        url: ROUTES.aiRanking,
        tone: "ai",
        blurb: "LLM Promise Scores on the institutional data. Local run and API key needed.",
      },
      {
        title: "Stock Due Diligence",
        code: "DD",
        icon: ClipboardCheck,
        url: ROUTES.aiDiligence,
        tone: "ai",
        blurb: "A due-diligence report on one ticker. Local run and API key needed.",
      },
    ],
  },
  {
    label: "Info",
    doors: [
      {
        title: "FAQ",
        code: "?",
        icon: BookOpen,
        url: ROUTES.learn,
        blurb: "How filings work, how funds are selected, what the numbers mean.",
      },
    ],
  },
  // Admin-only entries: local backend only, never on the public build.
  ...(LOCAL_DOORS.length ? [{ label: "Admin", doors: LOCAL_DOORS }] : []),
];

/** Every door of every section, flattened in menu order. */
export const MENU_DOORS: readonly MenuDoor[] = MENU_SECTIONS.flatMap((s) => s.doors);
