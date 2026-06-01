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
import GlobalSearch from "@/components/GlobalSearch";
import { Link, useLocation } from "react-router-dom";
import { APP_VERSION, BASE_PATH, IS_GH_PAGES_MODE } from "@/lib/config";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { cn } from "@/lib/utils";
import { ROUTES } from "@/lib/routes";
import { Sidebar, SidebarContent, SidebarFooter, useSidebar } from "@/components/ui/sidebar";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";

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
      { title: "Latest Filings", url: ROUTES.latest, icon: FileText },
      { title: "Quarterly Trends", url: ROUTES.quarterly, icon: BarChart3 },
      { title: "Hedge Fund Portfolios", url: ROUTES.funds, icon: Wallet },
      { title: "Stocks", url: ROUTES.stocks, icon: CandlestickChart },
    ],
  },
  {
    label: "AI-Powered",
    items: [
      { title: "Most Promising Stocks", url: ROUTES.aiRanking, icon: Search },
      { title: "Stock Due Diligence", url: ROUTES.aiDiligence, icon: ClipboardCheck },
    ],
  },
  // Configuration + Database are local-only — hidden entirely on the public
  // GH Pages build (no backend to write CSVs / manage funds / configure AI).
  ...(!IS_GH_PAGES_MODE
    ? [
        {
          label: "Configuration",
          items: [
            { title: "Funds Configuration", url: ROUTES.fundsConfig, icon: Settings2 },
            { title: "AI Settings", url: ROUTES.aiSettings, icon: Cpu },
          ],
        },
        {
          label: "Database",
          items: [{ title: "Update Operations", url: ROUTES.database, icon: Database }],
        },
      ]
    : []),
];

function isActiveUrl(pathname: string, url: string): boolean {
  if (url === ROUTES.stocks)
    return pathname === ROUTES.stocks || pathname.startsWith(`${ROUTES.stock}/`);
  // Word-boundary match: "/funds" must NOT match "/funds-config" — only itself
  // or its sub-routes like "/funds/<id>". Without the explicit "/" check the
  // startsWith greedy match highlights two sidebar items at once.
  return pathname === url || pathname.startsWith(`${url}/`);
}

/**
 * The shared navigation body — section list with the sliding active indicator
 * plus the data-freshness footer. Rendered in three contexts: the expanded
 * desktop rail, the collapsed icon-only desktop rail (`collapsed`), and the
 * mobile drawer. `onNavigate` lets the drawer close itself when a link is tapped.
 */
function SidebarNav({
  onNavigate,
  collapsed = false,
}: {
  onNavigate?: () => void;
  collapsed?: boolean;
}) {
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
  }, [location.pathname, collapsed]);
  /* eslint-enable @eslint-react/set-state-in-effect */

  return (
    <>
      <SidebarContent className={cn("pt-4 gap-0", collapsed ? "px-1.5" : "px-2")}>
        <div ref={navRef} className="relative">
          {/* Active item indicator — a single 2px hairline that slides between
              rows. Hidden when collapsed, where the active row's filled
              background is the affordance instead. */}
          {!collapsed && (
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
          )}

          {SECTIONS.map((section, sIdx) => (
            <div key={section.label} className={sIdx > 0 ? "mt-6" : ""}>
              {collapsed ? (
                // A short centred divider stands in for the section label.
                sIdx > 0 && (
                  <div className="mx-auto mb-2 h-px w-6 bg-sidebar-border/60" aria-hidden="true" />
                )
              ) : (
                <div className="px-3 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/45">
                      {section.label}
                    </span>
                    <span className="flex-1 h-px bg-sidebar-border/60" aria-hidden="true" />
                  </div>
                </div>
              )}
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
                        onClick={onNavigate}
                        title={collapsed ? item.title : undefined}
                        aria-label={collapsed ? item.title : undefined}
                        className={cn(
                          "group relative flex items-center rounded-md text-sm font-medium transition-all duration-150",
                          collapsed
                            ? "justify-center mx-auto my-0.5 h-10 w-10"
                            : "gap-3 mx-1 px-3 py-2.5 sm:py-2",
                          active
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-sidebar-foreground/70 hover:bg-sidebar-accent/40 hover:text-sidebar-foreground" +
                                (collapsed ? "" : " hover:translate-x-0.5"),
                        )}
                      >
                        <Icon
                          className={cn(
                            "h-4 w-4 shrink-0 transition-colors",
                            active
                              ? "text-primary"
                              : "text-sidebar-foreground/55 group-hover:text-sidebar-foreground/85",
                          )}
                          aria-hidden="true"
                        />
                        {!collapsed && <span className="truncate">{item.title}</span>}
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </SidebarContent>

      <SidebarFooter
        className={cn("py-3 border-t border-sidebar-border/60", collapsed ? "px-2" : "px-4")}
      >
        {collapsed ? (
          dataAsOfLabel && (
            <div className="flex justify-center" title={`Data as of ${dataAsOfLabel}`}>
              <span className="relative flex h-1.5 w-1.5 shrink-0">
                <span className="absolute inset-0 rounded-full bg-positive/60 animate-ping" />
                <span className="relative rounded-full h-1.5 w-1.5 bg-positive" />
              </span>
            </div>
          )
        ) : (
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
            <p className="text-[9px] tracking-wider text-sidebar-foreground/30">
              v{APP_VERSION} · by{" "}
              <a
                href="https://github.com/dokson"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-sidebar-foreground/60 transition-colors"
              >
                Alessandro Colace
              </a>
            </p>
          </div>
        )}
      </SidebarFooter>
    </>
  );
}

/**
 * Tablet/desktop (≥ md) navigation rail. Expanded (labels) by default; the
 * header toggle (or ⌘/Ctrl+B) collapses it to an icon-only rail and back, with
 * the choice persisted across reloads via SidebarProvider's cookie. It's a
 * normal flex child, so collapsing reclaims space for the content. Hidden on
 * phones, where navigation lives in <MobileSidebar /> instead.
 */
/**
 * Brand block at the top of the rail (logo + title). The framed logo doubles as
 * the collapse toggle (valuesnapshot-style) — clicking it expands/collapses the
 * rail; no separate hamburger. The h-16 height aligns with the content
 * top-navbar so the two top edges line up.
 */
function SidebarBrand({ collapsed }: { collapsed: boolean }) {
  const { toggleSidebar } = useSidebar();
  return (
    <div
      className={cn(
        "flex items-center h-16 border-b border-sidebar-border/60 shrink-0",
        collapsed ? "justify-center px-2" : "gap-2.5 px-3",
      )}
    >
      <button
        type="button"
        onClick={toggleSidebar}
        aria-label="Toggle sidebar"
        title="Toggle sidebar"
        className="shrink-0 grid place-items-center rounded-xl border border-sidebar-border bg-sidebar-accent/40 p-1 hover:bg-sidebar-accent hover:border-sidebar-foreground/30 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <img
          src={`${BASE_PATH}/logo-dark.png`}
          alt="Hedge Fund Tracker"
          className="h-11 w-11 rounded-lg hidden dark:block"
        />
        <img
          src={`${BASE_PATH}/logo-light.png`}
          alt="Hedge Fund Tracker"
          className="h-11 w-11 rounded-lg block dark:hidden"
        />
      </button>
      {!collapsed && (
        <Link to={ROUTES.home} className="min-w-0 leading-tight group/brand" title="Home">
          <p className="font-bold tracking-tight text-foreground truncate group-hover/brand:text-primary transition-colors">
            Hedge Fund Tracker
          </p>
          <p className="text-[10px] text-muted-foreground truncate">SEC filing analytics</p>
        </Link>
      )}
    </div>
  );
}

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  return (
    <Sidebar
      collapsible="none"
      className={cn(
        "hidden md:flex transition-[width] duration-200 ease-out",
        collapsed && "w-[4.25rem]",
      )}
    >
      <SidebarBrand collapsed={collapsed} />
      <SidebarNav collapsed={collapsed} />
    </Sidebar>
  );
}

/**
 * Phone navigation: an off-canvas drawer driven by the sidebar context's
 * openMobile flag (toggled by the header hamburger). Surfaces global search at
 * the top so the primary action is one tap away, mirroring app-style finance UIs.
 */
export function MobileSidebar() {
  const { openMobile, setOpenMobile } = useSidebar();
  const close = () => setOpenMobile(false);
  return (
    <Sheet open={openMobile} onOpenChange={setOpenMobile}>
      <SheetContent
        side="left"
        className="w-[18rem] max-w-[85vw] p-0 flex flex-col gap-0 bg-sidebar text-sidebar-foreground border-sidebar-border [&>button]:hidden"
      >
        <SheetTitle className="sr-only">Navigation</SheetTitle>
        <div className="flex items-center gap-2.5 px-4 h-14 border-b border-sidebar-border/60 shrink-0">
          <img
            src={`${BASE_PATH}/logo-dark.png`}
            alt="Hedge Fund Tracker"
            className="h-10 w-10 rounded-lg shrink-0 hidden dark:block"
          />
          <img
            src={`${BASE_PATH}/logo-light.png`}
            alt="Hedge Fund Tracker"
            className="h-10 w-10 rounded-lg shrink-0 block dark:hidden"
          />
          <span className="font-bold tracking-tight text-foreground truncate">
            Hedge Fund Tracker
          </span>
        </div>
        <div className="px-3 py-3 border-b border-sidebar-border/60 shrink-0">
          <GlobalSearch onNavigate={close} />
        </div>
        <div className="flex-1 min-h-0 flex flex-col overflow-y-auto">
          <SidebarNav onNavigate={close} />
        </div>
      </SheetContent>
    </Sheet>
  );
}
