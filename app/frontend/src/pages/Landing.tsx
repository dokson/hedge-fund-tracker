import { BASE_PATH } from "@/lib/config";
import { ROUTES } from "@/lib/routes";
import {
  ArrowRight,
  BarChart3,
  CandlestickChart,
  FileText,
  Sparkles,
  Star,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { Link } from "react-router-dom";

function Logo({ className = "" }: { className?: string }) {
  return <img src={`${BASE_PATH}/logo.png`} alt="Hedge Fund Tracker" className={className} />;
}

// Ordered fastest → slowest. `days` drives a shared-scale bar so the eye reads
// "how long until this filing is public": Form 4 a green sliver, 13F nearly full.
const FRESHNESS = [
  {
    tag: "Form 4",
    label: "Insider trades",
    days: 2,
    lag: "≈2 days",
    bar: "bg-positive",
    tone: "text-positive",
  },
  {
    tag: "13D/G",
    label: "Ownership changes",
    days: 10,
    lag: "≈10 days",
    bar: "bg-primary",
    tone: "text-primary",
  },
  {
    tag: "13F",
    label: "Quarterly snapshot",
    days: 45,
    lag: "≈45 days",
    bar: "bg-warning",
    tone: "text-warning",
  },
];
const MAX_LAG = 45;

const FEATURES: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: FileText,
    title: "Latest Filings",
    body: "The freshest institutional moves — 13D/G and Form 4 layered on the last 13F, with deltas vs the prior quarter.",
  },
  {
    icon: BarChart3,
    title: "Quarterly Trends",
    body: "Cross-fund consensus: who's accumulating, the new high-conviction names, and the biggest bets.",
  },
  {
    icon: Wallet,
    title: "Fund Portfolios",
    body: "Browse a curated roster of elite managers and see exactly what they hold, quarter by quarter.",
  },
  {
    icon: CandlestickChart,
    title: "Stock Analysis",
    body: "For any ticker: who owns it, how conviction is shifting, and the institutional money flow.",
  },
  {
    icon: Sparkles,
    title: "AI Promise Scores",
    body: "Top-tier LLMs rank the most promising names and run deep due diligence on high-conviction ideas.",
  },
  {
    icon: Star,
    title: "Your Watchlist",
    body: "Star the funds and stocks you follow for a personalized view across the whole platform.",
  },
];

export default function Landing() {
  return (
    <div className="mx-auto max-w-6xl">
      {/* ── Hero ── */}
      <section className="relative isolate text-center pt-12 sm:pt-20 pb-14">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            backgroundImage:
              "radial-gradient(55% 45% at 50% 0%, hsl(var(--primary) / 0.16), transparent 70%)",
          }}
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10 opacity-[0.04]"
          style={{
            backgroundImage:
              "linear-gradient(hsl(var(--foreground)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--foreground)) 1px, transparent 1px)",
            backgroundSize: "44px 44px",
            maskImage: "radial-gradient(65% 55% at 50% 0%, black, transparent 75%)",
          }}
        />

        <div className="mx-auto max-w-2xl px-4">
          <div
            className="inline-flex animate-in fade-in zoom-in-95 duration-700"
            style={{ filter: "drop-shadow(0 12px 40px hsl(var(--primary) / 0.35))" }}
          >
            <Logo className="h-40 w-40 sm:h-52 sm:w-52 rounded-2xl" />
          </div>

          <p
            className="mt-7 text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground animate-in fade-in slide-in-from-bottom-2 duration-700"
            style={{ animationDelay: "80ms", animationFillMode: "backwards" }}
          >
            Top 1% of funds · By track record alone
          </p>

          <h1
            className="mt-4 font-display text-4xl sm:text-6xl font-extrabold tracking-tight leading-[1.05] animate-in fade-in slide-in-from-bottom-3 duration-700"
            style={{ animationDelay: "140ms", animationFillMode: "backwards" }}
          >
            No Buffett. No Burry.
            <br />
            <span className="text-primary">Only the best track records.</span>
          </h1>

          <p
            className="mx-auto mt-6 max-w-xl text-base sm:text-lg text-muted-foreground leading-relaxed animate-in fade-in slide-in-from-bottom-3 duration-700"
            style={{ animationDelay: "220ms", animationFillMode: "backwards" }}
          >
            Forget the household names — Buffett, Ackman, Burry, Thiel and the rest. Hedge Fund
            Tracker follows only the top 1% of funds by historical track record, then turns their
            SEC filings into clear institutional signals — layered with the freshest ownership moves
            and ranked by AI.
          </p>

          <div
            className="mt-9 flex flex-col sm:flex-row items-center justify-center gap-3 animate-in fade-in slide-in-from-bottom-3 duration-700"
            style={{ animationDelay: "300ms", animationFillMode: "backwards" }}
          >
            <Link
              to={ROUTES.latest}
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3 text-base font-semibold text-primary-foreground shadow-lg shadow-primary/20 hover:opacity-90 transition-opacity w-full sm:w-auto justify-center"
            >
              Explore the dashboard <ArrowRight className="h-4 w-4" />
            </Link>
            <a
              href="https://github.com/dokson/hedge-fund-tracker"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-6 py-3 text-base font-medium text-foreground hover:border-foreground/30 transition-colors w-full sm:w-auto justify-center"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
              </svg>
              View on GitHub
            </a>
          </div>
        </div>
      </section>

      {/* ── The edge: data freshness ── */}
      <section className="px-4 py-12 sm:py-16">
        <div className="text-center max-w-2xl mx-auto">
          <span className="eyebrow text-primary">The edge</span>
          <h2 className="font-display text-2xl sm:text-3xl font-bold tracking-tight mt-2">
            A consensus that's actually current
          </h2>
          <p className="text-muted-foreground mt-3 leading-relaxed">
            Most 13F trackers show holdings that are 45+ days stale. We layer faster filings on top
            of the quarterly snapshot — so the picture reflects what funds are doing now.
          </p>
        </div>

        {/* Shared-scale "time to public" bars — same axis, so the lag is comparable */}
        <div className="surface max-w-2xl mx-auto p-6 sm:p-8 mt-9 space-y-5">
          {FRESHNESS.map((f) => (
            <div key={f.tag}>
              <div className="flex items-baseline justify-between gap-3 mb-2">
                <div className="flex items-baseline gap-2 min-w-0">
                  <span className="font-mono text-sm font-bold">{f.tag}</span>
                  <span className="text-xs text-muted-foreground truncate">{f.label}</span>
                </div>
                <span className={`font-mono text-sm font-semibold tabular-nums shrink-0 ${f.tone}`}>
                  {f.lag}
                </span>
              </div>
              <div className="h-2.5 rounded-full bg-muted/50 overflow-hidden">
                <div
                  className={`h-full rounded-full ${f.bar}`}
                  style={{ width: `${(f.days / MAX_LAG) * 100}%` }}
                />
              </div>
            </div>
          ))}
          <p className="pt-4 mt-1 border-t border-border/60 text-xs text-muted-foreground leading-relaxed">
            Each bar is the delay until that filing becomes public, on the same scale. We stack the
            fast ones — <span className="text-positive font-medium">Form 4</span> and{" "}
            <span className="text-primary font-medium">13D/G</span> — on top of the 45-day-old{" "}
            <span className="text-warning font-medium">13F</span>.
          </p>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="px-4 pb-12 sm:pb-16">
        <div className="text-center max-w-2xl mx-auto mb-9">
          <span className="eyebrow text-primary">Everything in one workspace</span>
          <h2 className="font-display text-2xl sm:text-3xl font-bold tracking-tight mt-2">
            From raw filings to a clear edge
          </h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="surface p-5 transition-colors hover:border-primary/40 group"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary group-hover:bg-primary/15 transition-colors">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="font-display font-semibold text-lg mt-4">{title}</h3>
              <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Final CTA ── */}
      <section className="px-4 pb-12">
        <div className="surface relative overflow-hidden p-8 sm:p-12 text-center">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 -z-10"
            style={{
              backgroundImage:
                "radial-gradient(50% 120% at 50% 0%, hsl(var(--primary) / 0.14), transparent 70%)",
            }}
          />
          <h2 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">
            Start exploring — right in your browser
          </h2>
          <p className="text-muted-foreground mt-3 max-w-xl mx-auto">
            No account, no setup. Open the dashboard and follow the institutional money today.
          </p>
          <Link
            to={ROUTES.latest}
            className="mt-7 inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3 text-base font-semibold text-primary-foreground shadow-lg shadow-primary/20 hover:opacity-90 transition-opacity"
          >
            Launch the app <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="px-4 pb-6 pt-2 text-center text-xs text-muted-foreground">
        Built by{" "}
        <a
          href="https://github.com/dokson"
          target="_blank"
          rel="noopener noreferrer"
          className="text-foreground hover:text-primary transition-colors"
        >
          Alessandro Colace
        </a>{" "}
        · Data from SEC EDGAR · Not investment advice.
      </footer>
    </div>
  );
}
