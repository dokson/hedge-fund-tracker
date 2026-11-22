import { Link, useLocation } from "react-router";

import { NavLink } from "@/components/NavLink";
import { BuildInfo } from "@/components/BuildInfo";
import { MENU_SECTIONS } from "@/lib/menuDoors";
import { cn } from "@/lib/utils";
import { ROUTES } from "@/lib/routes";
import { Sidebar, SidebarContent, SidebarFooter, useSidebar } from "@/components/ui/sidebar";
import { BrandLogo } from "@/components/ui/BrandLogo";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

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

  return (
    <>
      <SidebarContent className={cn("pt-3 gap-0", collapsed ? "px-1" : "px-2")}>
        <nav aria-label="Main menu">
          {MENU_SECTIONS.map((section, sIdx) => (
            <div key={section.label} className={sIdx > 0 ? "mt-4" : ""}>
              {collapsed ? (
                sIdx > 0 && <div className="mx-2 mb-2 h-px bg-border" aria-hidden="true" />
              ) : (
                <div className="px-3 mb-1.5 text-xs font-medium text-muted-foreground">
                  {section.label}
                </div>
              )}
              <ul>
                {section.doors.map((item) => {
                  const active = isActiveUrl(location.pathname, item.url);
                  const link = (
                    <NavLink
                      to={item.url}
                      end={item.url === ROUTES.home}
                      data-active={active}
                      onClick={onNavigate}
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
                  );
                  return (
                    <li key={item.url}>
                      {collapsed ? (
                        // The rail shows icons only: a tooltip, unlike `title`, also appears on keyboard focus.
                        <Tooltip>
                          <TooltipTrigger asChild>{link}</TooltipTrigger>
                          <TooltipContent side="right">{item.title}</TooltipContent>
                        </Tooltip>
                      ) : (
                        link
                      )}
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
        <BuildInfo compact={collapsed} />
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
    <div
      className={cn(
        // Same height as the top bar beside it, so the two rules form one line.
        "flex items-center h-14 border-b border-border shrink-0",
        collapsed ? "justify-center px-1" : "gap-1.5 px-3",
      )}
    >
      <button
        type="button"
        onClick={toggleSidebar}
        aria-label={collapsed ? "Expand menu" : "Collapse menu"}
        aria-expanded={!collapsed}
        className="shrink-0 grid place-items-center h-11 w-10 rounded-md transition-colors duration-[120ms] hover:bg-muted"
      >
        <BrandLogo size={36} className="h-9 w-9" />
      </button>
      {!collapsed && (
        <Link to={ROUTES.home} className="min-w-0 leading-tight group/brand" title="Home">
          <p className="text-base font-semibold tracking-tight text-foreground truncate">
            Hedge Fund Tracker
          </p>
          <p className="text-xs text-muted-foreground truncate">SEC 13F, 13D/G and Form 4</p>
        </Link>
      )}
    </div>
  );
}

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  // The rail's own landmark: the top bar is the page's single banner, and the
  // collapse toggle and wordmark stay inside a region (SC 1.3.1).
  return (
    <aside aria-label="Sidebar" className="hidden md:flex">
      <Sidebar
        collapsible="none"
        className={cn("border-r border-border", collapsed && "w-[3.5rem]")}
      >
        <SidebarBrand collapsed={collapsed} />
        <SidebarNav collapsed={collapsed} />
      </Sidebar>
    </aside>
  );
}
