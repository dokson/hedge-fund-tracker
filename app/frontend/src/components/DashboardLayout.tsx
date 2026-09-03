import { useState } from "react";
import { useLocation } from "react-router";
import { Sun, Moon, Search } from "lucide-react";
import { useTheme } from "next-themes";

import { AppSidebar } from "@/components/AppSidebar";
import { MobileNav } from "@/components/MobileNav";
import GlobalSearch from "@/components/GlobalSearch";
import MobileNotice from "@/components/MobileNotice";
import { GitHubMark } from "@/components/GitHubMark";
import { CoalesceCIcon } from "@/components/CoalesceCIcon";
import { SidebarProvider, useSidebar } from "@/components/ui/sidebar";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useAvailableQuarters } from "@/hooks/useAvailableQuarters";
import { APP_VERSION, BASE_PATH } from "@/lib/config";

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
  const { toggleSidebar } = useSidebar();
  return (
    <button
      type="button"
      onClick={toggleSidebar}
      aria-label="Open navigation"
      className="shrink-0 grid place-items-center h-9 w-9 rounded-md transition-colors duration-[120ms] hover:bg-muted"
    >
      <img src={`${BASE_PATH}/logo.png`} alt="" className="h-7 w-7" />
    </button>
  );
}

/** The top status line: board name, data vintage, version. */
function StatusLine() {
  const { latestQuarter } = useAvailableQuarters();
  const asOf = latestQuarter ? latestQuarter.replace("Q", " Q") : "…";
  return (
    <div className="status-line hidden lg:flex items-center gap-3 min-w-0 truncate">
      <span>
        <span className="k">Data as of</span> {asOf}
      </span>
      <span aria-hidden="true">·</span>
      <span>
        <span className="k">Source</span> SEC EDGAR
      </span>
      <span aria-hidden="true">·</span>
      <span>
        <span className="k">Version</span> {APP_VERSION}
      </span>
    </div>
  );
}

function IconAction({
  label,
  title,
  onClick,
  href,
  children,
}: {
  label: string;
  title?: string;
  onClick?: () => void;
  href?: string;
  children: React.ReactNode;
}) {
  const cls =
    "flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground transition-colors duration-[120ms] hover:text-foreground hover:bg-muted";
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

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { theme, setTheme } = useTheme();
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const location = useLocation();

  return (
    <SidebarProvider defaultOpen={readSidebarOpen()}>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-[60] focus:h-9 focus:inline-flex focus:items-center focus:px-3 focus:rounded-md bg-primary text-primary-foreground text-[13px] font-medium"
      >
        Skip to content
      </a>
      <MobileNav />
      <div className="h-screen flex w-full overflow-hidden">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-w-0">
          {/* Labelled: the sidebar brand plate is the other banner landmark. */}
          <header
            aria-label="Top bar"
            className="h-12 flex items-center gap-3 border-b border-border px-3 sm:px-4 shrink-0 bg-background z-10"
          >
            <div className="md:hidden">
              <HeaderLogo />
            </div>
            <div className="hidden md:block w-full max-w-md">
              <GlobalSearch />
            </div>
            <StatusLine />
            <div className="flex items-center shrink-0 ml-auto">
              <span className="md:hidden">
                <IconAction label="Search" onClick={() => setMobileSearchOpen(true)}>
                  <Search className="h-4 w-4" />
                </IconAction>
              </span>
              <IconAction
                label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              >
                <Sun className="h-4 w-4 hidden dark:block" />
                <Moon className="h-4 w-4 block dark:hidden" />
              </IconAction>
              <span className="hidden sm:block">
                <IconAction
                  label="GitHub repository"
                  href="https://github.com/dokson/hedge-fund-tracker"
                >
                  <GitHubMark className="h-4 w-4" />
                </IconAction>
              </span>
              <IconAction
                label="COalesCE website"
                title="COalesCE"
                href="https://www.coalesce.coach/en"
              >
                <CoalesceCIcon className="h-4 w-4" />
              </IconAction>
            </div>
          </header>

          <MobileNotice />

          <Sheet open={mobileSearchOpen} onOpenChange={setMobileSearchOpen}>
            <SheetContent side="top" className="p-3 pt-4 gap-0">
              <SheetTitle className="sr-only">Search</SheetTitle>
              {mobileSearchOpen && (
                <GlobalSearch focusOnMount onNavigate={() => setMobileSearchOpen(false)} />
              )}
            </SheetContent>
          </Sheet>

          {/* Keyed on the path so each screen mounts fresh on arrival. */}
          <main
            id="main"
            key={location.pathname}
            className="flex-1 overflow-auto p-3 sm:p-4 md:p-6"
          >
            {children}
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
