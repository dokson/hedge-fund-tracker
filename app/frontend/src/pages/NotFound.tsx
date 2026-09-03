import { useLocation, Link } from "react-router";
import { useEffect } from "react";
import { BarChart3, FileText, Home, LineChart, Wallet, type LucideIcon } from "lucide-react";

import { PanelTitle } from "@/components/ui/PanelTitle";
import { usePageMeta, pageTitle } from "@/hooks/usePageMeta";
import { ROUTES } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";

const RECOVERY: { label: string; path: string; icon: LucideIcon }[] = [
  { label: "Latest Filings", path: ROUTES.latest, icon: FileText },
  { label: "Quarterly Trends", path: ROUTES.quarterly, icon: BarChart3 },
  { label: "Stocks", path: ROUTES.stocks, icon: LineChart },
  { label: "Fund Portfolios", path: ROUTES.funds, icon: Wallet },
  { label: "Back to Home", path: ROUTES.home, icon: Home },
];

/** 404: what failed to resolve, then the routes that do. */
const NotFound = () => {
  const location = useLocation();
  const isSymbolLookup = location.pathname.startsWith("/stock/");

  usePageMeta({
    title: pageTitle("Page not found"),
    description:
      "This address did not resolve. Jump back to the filings board, the quarterly screens or the fund portfolios.",
    canonical: canonicalUrl(location.pathname),
  });

  useEffect(() => {
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="flex min-h-[72vh] items-center justify-center px-4 py-12">
      <div className="mx-auto w-full max-w-xl space-y-6">
        <h1 className="page-title">404 · Page not found</h1>

        <div className="frame">
          <div className="frame-title">
            <PanelTitle>
              {isSymbolLookup ? "No filings for this symbol" : "Route not found"}
            </PanelTitle>
          </div>
          <div className="space-y-3 p-3">
            <p className="flex min-w-0 items-center gap-2">
              <span className="sr-only">Requested route:</span>
              <code className="truncate rounded-sm bg-muted px-1.5 py-0.5 text-[13px] text-foreground">
                {location.pathname}
              </code>
            </p>
            <p className="text-[13px] text-muted-foreground">
              {isSymbolLookup
                ? "Nobody on the roster holds it, or the ticker was delisted before the last 13F."
                : "The address never resolved. It may have been renamed, or the link that brought you here is stale."}
            </p>
          </div>
        </div>

        <nav aria-label="Recovery routes" className="frame">
          <div className="frame-title">
            <PanelTitle>Go to</PanelTitle>
          </div>
          <ul className="divide-y divide-border/60">
            {RECOVERY.map(({ label, path, icon: Icon }) => (
              <li key={path}>
                <Link
                  to={path}
                  className="flex h-9 items-center gap-2 px-3 text-[13px] text-muted-foreground transition-colors duration-[120ms] hover:bg-muted hover:text-foreground hover:no-underline"
                >
                  <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <span className="truncate text-foreground">{label}</span>
                  <span className="ml-auto text-muted-foreground">{path}</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </div>
  );
};

export default NotFound;
