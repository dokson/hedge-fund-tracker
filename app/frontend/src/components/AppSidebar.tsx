import { useLayoutEffect, useRef, useState } from "react";
import {
  FileText,
  BarChart3,
  Wallet,
  Search,
  ClipboardCheck,
  CandlestickChart,
  Settings2,
  Cpu,
  Database,
  type LucideIcon,
} from "lucide-react";
import { NavLink } from "@/components/NavLink";
import { useLocation } from "react-router-dom";
import { APP_VERSION, IS_GH_PAGES_MODE } from "@/lib/config";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { Sidebar, SidebarContent, SidebarFooter } from "@/components/ui/sidebar";

interface NavItem {
  title: string;
  url: string;
  icon: LucideIcon;
}

interface NavSection {
  label: string;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    label: "Analysis",
    items: [
      { title: "Latest Filings", url: "/", icon: FileText },
      { title: "Quarterly Trends", url: "/quarterly", icon: BarChart3 },
      { title: "Hedge Fund Portfolios", url: "/funds", icon: Wallet },
      { title: "Stocks", url: "/stocks", icon: CandlestickChart },
    ],
  },
  {
    label: "AI-Powered",
    items: [
      { title: "Most Promising Stocks", url: "/ai-ranking", icon: Search },
      { title: "Stock Due Diligence", url: "/ai-diligence", icon: ClipboardCheck },
    ],
  },
  {
    label: "Configuration",
    items: [
      { title: "Funds Configuration", url: "/funds-config", icon: Settings2 },
      ...(!IS_GH_PAGES_MODE ? [{ title: "AI Settings", url: "/ai-settings", icon: Cpu }] : []),
    ],
  },
  ...(!IS_GH_PAGES_MODE
    ? [
        {
          label: "Database",
          items: [{ title: "Update Operations", url: "/database", icon: Database }],
        },
      ]
    : []),
];

function isActiveUrl(pathname: string, url: string): boolean {
  if (url === "/") return pathname === "/";
  if (url === "/stocks") return pathname === "/stocks" || pathname.startsWith("/stock/");
  // Word-boundary match: "/funds" must NOT match "/funds-config" — only itself
  // or its sub-routes like "/funds/<id>". Without the explicit "/" check the
  // startsWith greedy match highlights two sidebar items at once.
  return pathname === url || pathname.startsWith(`${url}/`);
}

export function AppSidebar() {
  const location = useLocation();
  const { latestQuarter } = useAvailableQuarters();
  const dataAsOfLabel = latestQuarter ? latestQuarter.replace("Q", " Q") : null;

  // Sliding active indicator: reads the active item's offsetTop / offsetHeight
  // from the DOM after layout so it adapts to any future copy / spacing change
  // without hardcoded row heights.
  const navRef = useRef<HTMLDivElement>(null);
  const [indicator, setIndicator] = useState<{ top: number; height: number } | null>(null);

  // Reads the active DOM node's geometry after layout to position the sliding
  // indicator — this is the canonical setState-in-effect use-case (syncing
  // React state with an external system, here the rendered DOM).
  /* eslint-disable @eslint-react/set-state-in-effect */
  useLayoutEffect(() => {
    if (!navRef.current) return;
    const activeEl = navRef.current.querySelector<HTMLElement>("[data-active='true']");
    if (!activeEl) {
      setIndicator(null);
      return;
    }
    setIndicator({
      top: activeEl.offsetTop + 8,
      height: activeEl.offsetHeight - 16,
    });
  }, [location.pathname]);
  /* eslint-enable @eslint-react/set-state-in-effect */

  return (
    <Sidebar collapsible="none">
      <SidebarContent className="pt-4 px-2 gap-0">
        <div ref={navRef} className="relative">
          {/* Active item indicator — a single 2px hairline that slides between rows */}
          <div
            aria-hidden="true"
            className="absolute left-0 w-[2px] rounded-full bg-primary transition-all duration-300 ease-out"
            style={{
              top: indicator?.top ?? 0,
              height: indicator?.height ?? 0,
              opacity: indicator ? 1 : 0,
              boxShadow: "0 0 12px hsl(var(--primary) / 0.5)",
            }}
          />

          {SECTIONS.map((section, sIdx) => (
            <div key={section.label} className={sIdx > 0 ? "mt-6" : ""}>
              <div className="px-3 mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-[9px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/45">
                    {section.label}
                  </span>
                  <span className="flex-1 h-px bg-sidebar-border/60" aria-hidden="true" />
                </div>
              </div>
              <ul className="space-y-0.5">
                {section.items.map((item) => {
                  const active = isActiveUrl(location.pathname, item.url);
                  const Icon = item.icon;
                  return (
                    <li key={item.url}>
                      <NavLink
                        to={item.url}
                        end={item.url === "/"}
                        data-active={active}
                        className={[
                          "group relative flex items-center gap-3 mx-1 px-3 py-2 rounded-md",
                          "text-sm font-medium transition-all duration-150",
                          active
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-sidebar-foreground/70 hover:bg-sidebar-accent/40 hover:text-sidebar-foreground hover:translate-x-0.5",
                        ].join(" ")}
                      >
                        <Icon
                          className={[
                            "h-4 w-4 shrink-0 transition-colors",
                            active
                              ? "text-primary"
                              : "text-sidebar-foreground/55 group-hover:text-sidebar-foreground/85",
                          ].join(" ")}
                          aria-hidden="true"
                        />
                        <span className="truncate">{item.title}</span>
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </SidebarContent>

      <SidebarFooter className="px-4 py-3 border-t border-sidebar-border/60">
        <div className="space-y-1.5">
          {dataAsOfLabel && (
            <div className="flex items-center gap-2">
              {/* Live data dot — pulses gently to signal a tracker that's "breathing" */}
              <span className="relative flex h-1.5 w-1.5 shrink-0">
                <span className="absolute inset-0 rounded-full bg-positive/60 animate-ping" />
                <span className="relative rounded-full h-1.5 w-1.5 bg-positive" />
              </span>
              <p className="text-[10px] font-medium tracking-wide text-sidebar-foreground/50">
                Data as of{" "}
                <span className="font-semibold text-sidebar-foreground/75">{dataAsOfLabel}</span>
              </p>
            </div>
          )}
          <p className="text-[9px] tracking-wider text-sidebar-foreground/30">v{APP_VERSION}</p>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
