import { useLocation, Link } from "react-router";
import { useEffect } from "react";
import { BarChart3, CandlestickChart, FileText, Home, SearchX, Wallet } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { ROUTES } from "@/lib/routes";

const RECOVERY: { icon: LucideIcon; label: string; path: string }[] = [
  { icon: FileText, label: "Latest Filings", path: ROUTES.latest },
  { icon: BarChart3, label: "Quarterly Trends", path: ROUTES.quarterly },
  { icon: CandlestickChart, label: "Stocks", path: ROUTES.stocks },
  { icon: Wallet, label: "Fund Portfolios", path: ROUTES.funds },
];

/**
 * 404 page, framed as a failed symbol lookup: the attempted route is quoted
 * back like a delisted ticker, followed by the real destinations.
 */
const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="relative isolate flex min-h-[72vh] items-center justify-center px-4 py-12">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          backgroundImage:
            "radial-gradient(50% 40% at 50% 8%, hsl(var(--negative) / 0.13), transparent 70%)",
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(hsl(var(--foreground)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--foreground)) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
          maskImage: "radial-gradient(60% 55% at 50% 10%, black, transparent 78%)",
        }}
      />

      <div className="mx-auto w-full max-w-xl text-center">
        <p
          className="eyebrow text-negative animate-in fade-in duration-700"
          style={{ animationFillMode: "backwards" }}
        >
          Error 404 · Route not found
        </p>

        <h1
          className="mt-3 font-display text-6xl sm:text-7xl font-extrabold tracking-tight leading-none animate-in fade-in slide-in-from-bottom-3 duration-700"
          style={{ animationDelay: "80ms", animationFillMode: "backwards" }}
        >
          404
        </h1>

        <p
          className="mt-4 font-display text-xl sm:text-2xl font-bold tracking-tight animate-in fade-in slide-in-from-bottom-3 duration-700"
          style={{ animationDelay: "140ms", animationFillMode: "backwards" }}
        >
          No filings for this symbol.
        </p>
        <p
          className="mx-auto mt-3 max-w-md text-sm sm:text-base text-muted-foreground leading-relaxed animate-in fade-in slide-in-from-bottom-3 duration-700"
          style={{ animationDelay: "200ms", animationFillMode: "backwards" }}
        >
          The route you asked for never resolved. It may have been renamed, or the link that brought
          you here is stale.
        </p>

        {/* The attempted path, quoted back like a delisted ticker line */}
        <div
          className="surface mt-8 flex items-center gap-3 p-4 text-left animate-in fade-in slide-in-from-bottom-3 duration-700"
          style={{ animationDelay: "260ms", animationFillMode: "backwards" }}
        >
          <SearchX className="h-5 w-5 shrink-0 text-negative" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="metric-label">Requested route</p>
            <p className="mt-0.5 truncate font-mono text-sm font-semibold text-foreground">
              {location.pathname}
            </p>
          </div>
          <span className="shrink-0 inline-flex items-center rounded bg-negative/15 px-1.5 py-0.5 font-mono text-xs font-semibold text-negative">
            NOT FOUND
          </span>
        </div>

        <div
          className="mt-8 animate-in fade-in slide-in-from-bottom-3 duration-700"
          style={{ animationDelay: "320ms", animationFillMode: "backwards" }}
        >
          <Link
            to={ROUTES.home}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3 text-base font-semibold text-primary-foreground shadow-lg shadow-primary/20 transition-opacity hover:opacity-90"
          >
            <Home className="h-4 w-4" aria-hidden="true" />
            Back to Home
          </Link>
        </div>

        <div
          className="mt-10 animate-in fade-in slide-in-from-bottom-3 duration-700"
          style={{ animationDelay: "380ms", animationFillMode: "backwards" }}
        >
          <p className="metric-label">Or jump to</p>
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {RECOVERY.map(({ icon: Icon, label, path }) => (
              <Link
                key={path}
                to={path}
                className="group flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 text-left transition-colors hover:border-foreground/30"
              >
                <Icon
                  className="h-4 w-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary"
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1 text-sm font-medium text-foreground">{label}</span>
                <span className="shrink-0 font-mono text-xs text-muted-foreground">{path}</span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default NotFound;
