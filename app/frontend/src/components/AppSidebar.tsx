import { Link, useLocation } from "react-router";

import { NavLink } from "@/components/NavLink";
import { APP_VERSION, BASE_PATH } from "@/lib/config";
import { MENU_SECTIONS } from "@/lib/menuDoors";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { cn } from "@/lib/utils";
import { ROUTES } from "@/lib/routes";
import { Sidebar, SidebarContent, SidebarFooter, useSidebar } from "@/components/ui/sidebar";

function isActiveUrl(pathname: string, url: string): boolean {
  if (url === ROUTES.stocks)
    return pathname === ROUTES.stocks || pathname.startsWith(`${ROUTES.stock}/`);
  return pathname === url || pathname.startsWith(`${url}/`);
}

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

  return (
    <>
      <SidebarContent className={cn("pt-3 gap-0", collapsed ? "px-1" : "px-2")}>
        <nav aria-label="Main menu">
          {MENU_SECTIONS.map((section, sIdx) => (
            <div key={section.label} className={sIdx > 0 ? "mt-4" : ""}>
              {collapsed ? (
                sIdx > 0 && <div className="mx-2 mb-2 h-px bg-border" aria-hidden="true" />
              ) : (
                <div className="px-3 mb-1 text-[11px] text-muted-foreground">{section.label}</div>
              )}
              <ul>
                {section.doors.map((item) => {
                  const active = isActiveUrl(location.pathname, item.url);
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
                          "menu-line",
                          collapsed && "justify-center px-0",
                          item.tone === "ai" && !active && "text-magenta",
                        )}
                      >
                        <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                        {!collapsed && <span className="truncate">{item.title}</span>}
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </SidebarContent>

      <SidebarFooter
        className={cn("py-2 border-t border-border status-line", collapsed ? "px-1" : "px-3")}
      >
        {/* The data-freshness line and the version/copyright line sat outside
            every landmark (SC 1.3.1, axe `region`). */}
        <footer aria-label="Dataset and version">
          {collapsed ? (
            dataAsOfLabel && (
              <div className="flex justify-center" title={`Data as of ${dataAsOfLabel}`}>
                <span className="h-2 w-2 bg-positive" aria-hidden="true" />
              </div>
            )
          ) : (
            <div className="space-y-0 text-xs">
              {dataAsOfLabel && (
                <p className="flex items-center gap-2 truncate">
                  <span className="h-2 w-2 bg-positive shrink-0" aria-hidden="true" />
                  <span>
                    <span className="k">Data</span> {dataAsOfLabel}
                  </span>
                </p>
              )}
              <p className="truncate text-muted-foreground">
                v{APP_VERSION} · ©{" "}
                <a
                  href="https://www.coalesce.coach/en"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="COalesCE website"
                  className="underline underline-offset-2 hover:text-foreground"
                >
                  COalesCE
                </a>
              </p>
            </div>
          )}
        </footer>
      </SidebarFooter>
    </>
  );
}

/**
 * Brand plate at the top of the rail. The mark is the collapse toggle; the
 * wordmark links home. Same height as the content top bar so the rules meet.
 */
function SidebarBrand({ collapsed }: { collapsed: boolean }) {
  const { toggleSidebar } = useSidebar();
  return (
    // A landmark, so the wordmark and the collapse toggle are not orphaned
    // outside every region (SC 1.3.1, axe `region`). Labelled because the
    // content top bar is the other banner on the page.
    <header
      aria-label="Sidebar"
      className={cn(
        "flex items-center h-12 border-b border-border shrink-0",
        collapsed ? "justify-center px-1" : "gap-2 px-3",
      )}
    >
      <button
        type="button"
        onClick={toggleSidebar}
        aria-label={collapsed ? "Expand menu" : "Collapse menu"}
        aria-expanded={!collapsed}
        className="shrink-0 grid place-items-center h-9 w-9 rounded-md transition-colors duration-[120ms] hover:bg-muted"
      >
        <img src={`${BASE_PATH}/logo.png`} alt="" className="h-7 w-7" />
      </button>
      {!collapsed && (
        <Link to={ROUTES.home} className="min-w-0 leading-none group/brand" title="Home">
          <p className="text-sm font-semibold text-foreground truncate">Hedge Fund Tracker</p>
          <p className="text-[11px] text-muted-foreground truncate">SEC 13F · 13D/G · Form 4</p>
        </Link>
      )}
    </header>
  );
}

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  return (
    <Sidebar
      collapsible="none"
      className={cn("hidden md:flex border-r border-border", collapsed && "w-[3.5rem]")}
    >
      <SidebarBrand collapsed={collapsed} />
      <SidebarNav collapsed={collapsed} />
    </Sidebar>
  );
}
