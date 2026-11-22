import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router";
import { House, Search } from "lucide-react";
import { useTheme } from "next-themes";

import { AppSidebar } from "@/components/AppSidebar";
import { MobileNav } from "@/components/MobileNav";
import GlobalSearch from "@/components/GlobalSearch";
import { GitHubLink } from "@/components/GitHubLink";
import { ThemeSwitch } from "@/components/ThemeSwitch";
import { CoalesceCIcon } from "@/components/CoalesceCIcon";
import { SidebarProvider, useSidebar } from "@/components/ui/sidebar";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useResearchScrollRestoration } from "@/hooks/useResearchScrollRestoration";
import { ROUTES } from "@/lib/routes";
import { announce, APP_STATUS_ID } from "@/lib/announce";
import { BrandLogo } from "@/components/ui/BrandLogo";

/**
 * Restore the desktop rail's expanded/collapsed choice from the cookie that
 * SidebarProvider writes on every toggle, so it survives reloads.
 */
function readSidebarOpen(): boolean {
  if (typeof document === "undefined") return true;
  const match = document.cookie.match(/(?:^|; )sidebar:state=([^;]+)/);
  return match ? match[1] !== "false" : true;
}

/** On phones the mark opens the nav drawer; there is no hamburger. */
function HeaderLogo() {
  const { toggleSidebar, openMobile } = useSidebar();
  return (
    <button
      type="button"
      onClick={toggleSidebar}
      aria-label="Open navigation"
      aria-haspopup="dialog"
      aria-expanded={openMobile}
      className="shrink-0 grid place-items-center h-10 w-10 rounded-md transition-colors duration-[120ms] hover:bg-muted"
    >
      <BrandLogo size={32} className="h-8 w-8" />
    </button>
  );
}

function IconAction({
  label,
  title,
  onClick,
  href,
  to,
  children,
}: {
  label: string;
  title?: string;
  onClick?: () => void;
  href?: string;
  to?: string;
  children: React.ReactNode;
}) {
  const cls =
    "flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground transition-colors duration-[120ms] hover:text-foreground hover:bg-muted";
  if (to) {
    return (
      <Link to={to} className={cls} aria-label={label} title={title}>
        {children}
      </Link>
    );
  }
  if (href) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className={cls}
        aria-label={label}
        title={title}
      >
        {children}
      </a>
    );
  }
  return (
    <button type="button" onClick={onClick} className={cls} aria-label={label} title={title}>
      {children}
    </button>
  );
}

// Mirrors --background in index.css; the browser UI colour cannot read CSS variables.
const THEME_COLOR = { dark: "#0e1320", light: "#ffffff" } as const;

/**
 * The app's one status region: it announces the new page title after a client-side
 * navigation (which fires no load event), and `announce()` speaks through it too.
 */
function StatusRegion() {
  useEffect(() => {
    const title = document.querySelector("title");
    if (!title) return;
    const observer = new MutationObserver(() => announce(document.title));
    observer.observe(title, { childList: true, characterData: true, subtree: true });
    return () => observer.disconnect();
  }, []);
  // No React children: the text is written by `announce()`, so a re-render never wipes it.
  return <div id={APP_STATUS_ID} role="status" className="sr-only" />;
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { resolvedTheme, systemTheme, setTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  // Flip what is rendered; landing back on the OS scheme returns to "system"
  // instead of pinning it, so the visitor is never stuck against the OS.
  const toggleTheme = () => {
    const next = isDark ? "light" : "dark";
    setTheme(next === systemTheme ? "system" : next);
  };
  useEffect(() => {
    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
    if (meta && resolvedTheme)
      meta.content = resolvedTheme === "dark" ? THEME_COLOR.dark : THEME_COLOR.light;
  }, [resolvedTheme]);
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const [showHeaderStars, setShowHeaderStars] = useState(false);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(min-width: 640px)");
    const update = () => setShowHeaderStars(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  useResearchScrollRestoration(mainRef);

  return (
    <SidebarProvider defaultOpen={readSidebarOpen()}>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-[60] focus:h-9 focus:inline-flex focus:items-center focus:px-3 focus:rounded-md bg-primary text-primary-foreground text-[13px] font-medium"
      >
        Skip to content
      </a>
      <MobileNav />
      <StatusRegion />
      {/* Phones scroll the document so the browser chrome can collapse. */}
      <div className="flex w-full md:h-screen md:overflow-clip">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-w-0 md:min-h-0">
          {/* Labelled: the sidebar brand plate is the other banner landmark. */}
          <header
            aria-label="Top bar"
            // 56px: the bar carries the brand beside it, so it gets the room the mark needs;
            // `scroll-padding-top: 3.5rem` in index.css matches it.
            className="sticky top-0 h-14 flex items-center gap-3 border-b border-border px-3 sm:px-4 shrink-0 bg-background z-10"
          >
            <div className="md:hidden">
              <HeaderLogo />
            </div>
            <div className="hidden md:block w-full max-w-xl">
              <GlobalSearch />
            </div>
            <div className="flex items-center shrink-0 ml-auto">
              <span className="md:hidden">
                <IconAction label="Home" to={ROUTES.home}>
                  <House className="h-4 w-4" />
                </IconAction>
              </span>
              <span className="md:hidden">
                <IconAction label="Search" onClick={() => setMobileSearchOpen(true)}>
                  <Search className="h-4 w-4" />
                </IconAction>
              </span>
              <ThemeSwitch isDark={isDark} onToggle={toggleTheme} className="mx-1" />
              <GitHubLink className="mx-1 hidden sm:inline-flex" enabled={showHeaderStars} />
              <IconAction
                label="COalesCE website"
                title="COalesCE"
                href="https://www.coalesce.coach/en"
              >
                <CoalesceCIcon className="h-4 w-4" />
              </IconAction>
            </div>
          </header>

          <Sheet open={mobileSearchOpen} onOpenChange={setMobileSearchOpen}>
            <SheetContent
              side="top"
              className="max-h-[100dvh] flex-col overflow-clip p-3 pt-4 pr-14 open:flex open:gap-0"
            >
              <SheetTitle className="sr-only">Search</SheetTitle>
              {mobileSearchOpen && (
                <GlobalSearch inline focusOnMount onNavigate={() => setMobileSearchOpen(false)} />
              )}
            </SheetContent>
          </Sheet>

          {/* Keyed on the path so each screen mounts fresh on arrival. */}
          <main
            id="main"
            ref={mainRef}
            key={location.pathname}
            tabIndex={-1}
            className="relative flex-1 min-w-0 p-3 sm:p-4 md:p-6 md:overflow-auto focus:outline-none"
          >
            {children}
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
