import { useEffect } from "react";
import { X } from "lucide-react";
import { Link, useLocation } from "react-router";

import GlobalSearch from "@/components/GlobalSearch";
import { NavLink } from "@/components/NavLink";
import { BuildInfo } from "@/components/BuildInfo";
import { Dialog, DialogClose, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { MENU_SECTIONS } from "@/lib/menuDoors";
import { ROUTES } from "@/lib/routes";
import { useSidebar } from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";
import { BrandLogo } from "@/components/ui/BrandLogo";
import { DIALOG_AUTOFOCUS } from "@/lib/dialog";

function isActiveUrl(pathname: string, url: string): boolean {
  if (url === ROUTES.stocks)
    return pathname === ROUTES.stocks || pathname.startsWith(`${ROUTES.stock}/`);
  return pathname === url || pathname.startsWith(`${url}/`);
}

/**
 * Phone navigation: a full-screen overlay, not an off-canvas drawer. A 288px
 * drawer left the board visible behind it and gave the rows a desktop-sized
 * hit area; the overlay owns the viewport and the rows are 44px touch targets.
 *
 * The native modal handles focus, Escape, and the inert background. Route
 * changes and viewport changes close it when navigation moves elsewhere.
 */
export function MobileNav() {
  const { openMobile, setOpenMobile, isMobile } = useSidebar();
  const location = useLocation();
  const close = () => setOpenMobile(false);

  // Back/forward navigation fires no click, so close the overlay on route changes.
  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect
    setOpenMobile(false);
    // `setOpenMobile` is a stable setState, so it never re-fires the effect.
  }, [location.pathname, setOpenMobile]);

  // Growing past the phone breakpoint hands navigation back to the desktop rail.
  useEffect(() => {
    if (!isMobile && openMobile) setOpenMobile(false);
  }, [isMobile, openMobile, setOpenMobile]);

  return (
    <Dialog open={openMobile} onOpenChange={setOpenMobile}>
      <DialogContent
        showCloseButton={false}
        className={cn(
          "fixed inset-0 z-50 m-0 h-dvh max-h-none w-screen max-w-none translate-x-0 translate-y-0 flex-col gap-0 overflow-hidden rounded-none border-0 bg-background p-0 text-foreground shadow-none open:flex",
          "duration-[120ms] motion-reduce:duration-0",
        )}
      >
        <DialogTitle className="sr-only">Navigation</DialogTitle>

        <div className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-3">
          <Link
            to={ROUTES.home}
            onClick={close}
            className="flex min-w-0 items-center gap-2 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <BrandLogo size={32} className="h-8 w-8 shrink-0" />
            <span className="truncate text-base font-semibold text-foreground">
              Hedge Fund Tracker
            </span>
          </Link>
          <DialogClose
            {...DIALOG_AUTOFOCUS}
            aria-label="Close navigation"
            className="ml-auto grid h-11 w-11 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors duration-[120ms] hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </DialogClose>
        </div>

        <div className="flex min-h-0 shrink flex-col border-b border-border px-3 py-3">
          <GlobalSearch inline onNavigate={close} />
        </div>

        <nav aria-label="Main menu" className="min-h-0 flex-1 overflow-y-auto px-2 py-3">
          {MENU_SECTIONS.map((section, sIdx) => (
            <div key={section.label} className={sIdx > 0 ? "mt-5" : ""}>
              <div className="px-3 pb-1 text-[11px] text-muted-foreground">{section.label}</div>
              <ul>
                {section.doors.map((item) => {
                  const active = isActiveUrl(location.pathname, item.url);
                  return (
                    <li key={item.url}>
                      <NavLink
                        to={item.url}
                        end={item.url === ROUTES.home}
                        data-active={active}
                        onClick={close}
                        className={cn(
                          "menu-line h-auto min-h-11 items-start gap-3 px-3 py-2.5",
                          item.tone === "ai" && !active && "text-magenta",
                        )}
                      >
                        <item.icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
                        <span className="min-w-0">
                          <span className="block text-[16px] leading-6 text-foreground">
                            {item.title}
                          </span>
                          {item.blurb && (
                            <span className="mt-0.5 block text-[12px] leading-4 text-muted-foreground">
                              {item.blurb}
                            </span>
                          )}
                        </span>
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <footer
          aria-label="Dataset and version"
          className="shrink-0 border-t border-border px-4 py-2"
        >
          <BuildInfo />
        </footer>
      </DialogContent>
    </Dialog>
  );
}

export default MobileNav;
