import { useEffect, useRef } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useLocation } from "react-router";

import GlobalSearch from "@/components/GlobalSearch";
import { NavLink } from "@/components/NavLink";
import { APP_VERSION, BASE_PATH } from "@/lib/config";
import { MENU_SECTIONS } from "@/lib/menuDoors";
import { ROUTES } from "@/lib/routes";
import { useSidebar } from "@/components/ui/sidebar";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { cn } from "@/lib/utils";

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
 * Radix Dialog is the primitive rather than a hand-rolled layer: it already
 * ships the focus trap, Escape, the body scroll lock, `aria-modal` and
 * `aria-hidden` on everything outside the portal, and it restores focus to the
 * element that was focused when it opened — the header toggle. What it cannot
 * know is added here: closing on a route change (browser back/forward fires no
 * click), `inert` on the page behind (belt to the aria-hidden braces, and what
 * keeps the MobileNotice row unreachable), and closing when the viewport grows
 * past the phone breakpoint.
 */
export function MobileNav() {
  const { openMobile, setOpenMobile, isMobile } = useSidebar();
  const location = useLocation();
  const closeRef = useRef<HTMLButtonElement>(null);
  /** Whatever was focused when the overlay opened — the header toggle. */
  const openerRef = useRef<HTMLElement | null>(null);
  const { latestQuarter } = useAvailableQuarters();
  const dataAsOfLabel = latestQuarter ? latestQuarter.replace("Q", " Q") : null;
  const close = () => setOpenMobile(false);

  // Back/forward navigation fires no click, so nothing else would close the
  // overlay and it would sit over the new page with the scroll still locked.
  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect
    setOpenMobile(false);
    // `setOpenMobile` is a stable setState, so it never re-fires the effect.
  }, [location.pathname, setOpenMobile]);

  // Growing past the phone breakpoint hands navigation back to the desktop rail.
  useEffect(() => {
    if (!isMobile && openMobile) setOpenMobile(false);
  }, [isMobile, openMobile, setOpenMobile]);

  // The overlay is opaque, but the content behind it stays in the DOM: `inert`
  // takes it out of the tab order AND out of the screen-reader browse cursor,
  // which a focus trap alone does not do.
  useEffect(() => {
    if (!openMobile) return;
    openerRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const behind = [
      document.getElementById("main"),
      document.querySelector<HTMLElement>("header[aria-label='Top bar']"),
      document.querySelector<HTMLElement>("[role='status']"),
    ].filter((n): n is HTMLElement => n !== null);
    for (const el of behind) el.inert = true;
    return () => {
      for (const el of behind) el.inert = false;
    };
  }, [openMobile]);

  return (
    <DialogPrimitive.Root open={openMobile} onOpenChange={setOpenMobile}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Content
          aria-label="Navigation"
          // Focus lands on the close button, not on the search field: focusing
          // an input here pops the on-screen keyboard over the menu the visitor
          // just asked to see.
          onOpenAutoFocus={(e) => {
            e.preventDefault();
            closeRef.current?.focus();
          }}
          // Radix restores focus to its Trigger, and there is none here: the
          // toggle lives in the header. Closing must always hand focus back to
          // it (SC 2.4.3), whether by Escape, the X or a link.
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            openerRef.current?.focus();
          }}
          className={cn(
            "fixed inset-0 z-50 flex flex-col bg-background text-foreground md:hidden",
            "duration-[120ms] data-[state=open]:animate-in data-[state=open]:fade-in-0",
            "motion-reduce:animate-none motion-reduce:duration-0",
          )}
        >
          <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>

          <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-3">
            <img src={`${BASE_PATH}/logo.png`} alt="" className="h-7 w-7 shrink-0" />
            <span className="truncate text-sm font-semibold text-foreground">
              Hedge Fund Tracker
            </span>
            <button
              ref={closeRef}
              type="button"
              onClick={close}
              aria-label="Close navigation"
              className="ml-auto grid h-11 w-11 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors duration-[120ms] hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>

          <div className="shrink-0 border-b border-border px-3 py-3">
            <GlobalSearch onNavigate={close} />
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
                          end={item.url === "/"}
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
            className="status-line shrink-0 border-t border-border px-4 py-2 text-xs"
          >
            {dataAsOfLabel && (
              <p className="flex items-center gap-2 truncate">
                <span className="h-2 w-2 shrink-0 bg-positive" aria-hidden="true" />
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
                className="underline underline-offset-2 hover:text-foreground"
              >
                COalesCE
              </a>
            </p>
          </footer>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export default MobileNav;
