import { useState } from "react";
import { AppSidebar, MobileSidebar } from "@/components/AppSidebar";
import GlobalSearch from "@/components/GlobalSearch";
import { SidebarProvider, useSidebar } from "@/components/ui/sidebar";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Sun, Moon, Search } from "lucide-react";
import { useTheme } from "next-themes";
import { BASE_PATH } from "@/lib/config";

/**
 * Restore the desktop rail's expanded/collapsed choice from the cookie that
 * SidebarProvider writes on every toggle, so it survives reloads.
 */
function readSidebarOpen(): boolean {
  if (typeof document === "undefined") return true;
  const match = document.cookie.match(/(?:^|; )sidebar:state=([^;]+)/);
  return match ? match[1] !== "false" : true;
}

/**
 * The brand logo doubles as the sidebar toggle (valuesnapshot-style): clicking
 * it collapses/expands the desktop rail, and opens the drawer on mobile — so
 * there's no separate hamburger. Must live inside SidebarProvider to read the
 * toggle. Theme-aware: transparent cyan mark on dark, dark badge on light.
 */
function HeaderLogo() {
  const { toggleSidebar } = useSidebar();
  return (
    <button
      type="button"
      onClick={toggleSidebar}
      aria-label="Toggle sidebar"
      title="Toggle sidebar"
      className="shrink-0 grid place-items-center rounded-xl border border-border bg-card p-1 hover:bg-accent/30 hover:border-foreground/30 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <img
        src={`${BASE_PATH}/logo.png`}
        alt="Hedge Fund Tracker"
        className="h-12 w-12 rounded-lg"
      />
    </button>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { theme, setTheme } = useTheme();
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  return (
    <SidebarProvider defaultOpen={readSidebarOpen()}>
      <MobileSidebar />
      {/* valuesnapshot-style shell: full-height sidebar (brand at its top) on the
          left, and a content column whose own top-navbar holds the search. */}
      <div className="h-screen flex w-full overflow-hidden">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <header className="h-16 flex items-center gap-2 sm:gap-3 border-b border-border px-3 sm:px-5 shrink-0 bg-background z-10">
            {/* Phones have no rail — the logo opens the nav drawer instead. */}
            <div className="md:hidden">
              <HeaderLogo />
            </div>
            <div className="hidden md:block w-full max-w-md">
              <GlobalSearch />
            </div>
            <div className="flex items-center gap-1 sm:gap-3 shrink-0 ml-auto">
              {/* Phone-only search: opens a full-width sheet so the field gets the
                  whole viewport and the keyboard, instead of cramming into the bar. */}
              <button
                onClick={() => setMobileSearchOpen(true)}
                className="md:hidden flex h-9 w-9 items-center justify-center text-muted-foreground hover:text-foreground transition-colors rounded-md"
                aria-label="Search"
              >
                <Search className="h-5 w-5" />
              </button>
              <button
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                className="flex h-9 w-9 items-center justify-center text-muted-foreground hover:text-foreground transition-colors rounded-md cursor-pointer"
                aria-label="Toggle theme"
              >
                <Sun className="h-5 w-5 hidden dark:block" />
                <Moon className="h-5 w-5 block dark:hidden" />
              </button>
              <a
                href="https://github.com/dokson/hedge-fund-tracker"
                target="_blank"
                rel="noopener noreferrer"
                className="hidden sm:flex h-9 w-9 items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
                aria-label="GitHub repository"
              >
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
                </svg>
              </a>
            </div>
          </header>

          {/* Phone search sheet */}
          <Sheet open={mobileSearchOpen} onOpenChange={setMobileSearchOpen}>
            <SheetContent side="top" className="p-4 pt-5 gap-0 [&>button]:hidden">
              <SheetTitle className="sr-only">Search</SheetTitle>
              {mobileSearchOpen && (
                <GlobalSearch focusOnMount onNavigate={() => setMobileSearchOpen(false)} />
              )}
            </SheetContent>
          </Sheet>

          <main className="flex-1 overflow-auto p-3 sm:p-4 md:p-6">{children}</main>
        </div>
      </div>
    </SidebarProvider>
  );
}
