// vitest/config wraps Vite's defineConfig with the `test` key typed
// deliberately (not via incidental module augmentation).
import { defineConfig } from "vitest/config";
import type { Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "fs";
import Papa from "papaparse";

import {
  buildFundSummaries,
  buildStockSummaries,
  fundEntityPage,
  parseReportedValue,
  renderFundBody,
  renderStockBody,
  stockEntityPage,
  type FundMeta,
  type QuarterRow,
  type TrackPoint,
} from "./src/lib/entityPages.ts";
import { ABOUT_LAST_UPDATED, renderAboutBody } from "./src/lib/aboutContent.ts";
import { ROUTES } from "./src/lib/routes.ts";
import { FAQ_LAST_UPDATED, FAQ_META, FAQ_SECTIONS } from "./src/lib/faqContent.ts";
import {
  ABOUT_PAGE,
  FUNDS_PAGE,
  HOME_PAGE,
  LEARN_PAGE,
  PERFORMANCE_PAGE,
  PUBLIC_PAGES,
  STOCKS_PAGE,
  type PublicPage,
} from "./src/lib/pageMeta.ts";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildHomeJsonLd,
  buildSitemap,
  canonicalUrl,
  escapeAttr,
  escapeHtml,
  latestCsvDate,
  renderFaqStaticHtml,
  renderPageBody,
  renderStaticPage,
  SITE_BASE,
  SITE_ORIGIN,
  staticFileFor,
} from "./src/lib/seo.ts";

// Single source-of-truth for the app version: app/frontend/package.json. The
// backend reads the same field at request time (see app/utils/version.py) so
// every surface (sidebar footer, server /health, GH release tag) agrees.
const pkg: unknown = JSON.parse(
  readFileSync(path.resolve(import.meta.dirname, "package.json"), "utf-8"),
);
if (
  typeof pkg !== "object" ||
  pkg === null ||
  !("version" in pkg) ||
  typeof pkg.version !== "string"
) {
  throw new Error("package.json is missing a string `version` field");
}
const APP_VERSION: string = pkg.version;

const DATABASE_DIR = path.resolve(import.meta.dirname, "../../database");

/** Latest date in a repo database/ CSV column; null when the file is absent. */
function databaseDate(file: string, column: string): string | null {
  const csvPath = path.resolve(DATABASE_DIR, file);
  return existsSync(csvPath) ? latestCsvDate(readFileSync(csvPath, "utf-8"), column) : null;
}

function readCsv(file: string): Record<string, string>[] {
  return Papa.parse<Record<string, string>>(readFileSync(file, "utf-8"), {
    header: true,
    skipEmptyLines: true,
  }).data;
}

/** The newest quarter's per-fund rows plus the fund and company masters. */
function loadLatestQuarter(): {
  quarter: string;
  rows: QuarterRow[];
  funds: FundMeta[];
  companies: Record<string, string>;
} | null {
  if (!existsSync(DATABASE_DIR)) return null;
  const quarter = readdirSync(DATABASE_DIR)
    .filter((name) => /^\d{4}Q[1-4]$/.test(name))
    .sort()
    .at(-1);
  if (!quarter) return null;
  const quarterDir = path.resolve(DATABASE_DIR, quarter);
  const rows = readdirSync(quarterDir)
    .filter((name) => name.endsWith(".csv"))
    .flatMap((name) =>
      readCsv(path.resolve(quarterDir, name)).map((r) => ({
        // Same mapping as fileNameToFundName (lib/data/funds.ts imports browser fetch code).
        fund: name.slice(0, -".csv".length).replace(/_/g, " "),
        ticker: r.Ticker ?? "",
        company: r.Company ?? "",
        value: parseReportedValue(r.Value ?? ""),
        portfolioPct: Number.parseFloat(r["Portfolio%"] ?? "") || 0,
        delta: r.Delta ?? "",
      })),
    );
  const funds = readCsv(path.resolve(DATABASE_DIR, "hedge_funds.csv")).map((r) => ({
    fund: r.Fund ?? "",
    manager: r.Manager ?? "",
    denomination: r.Denomination ?? "",
  }));
  const companies: Record<string, string> = {};
  for (const r of readCsv(path.resolve(DATABASE_DIR, "stocks.csv"))) {
    if (r.Ticker && r.Company && !companies[r.Ticker]) companies[r.Ticker] = r.Company;
  }
  return { quarter, rows, funds, companies };
}

/** Each fund's quarterly track record from fund_performance.csv, oldest first. */
function loadFundTracks(): Map<string, TrackPoint[]> {
  const tracks = new Map<string, TrackPoint[]>();
  const file = path.resolve(DATABASE_DIR, "fund_performance.csv");
  if (!existsSync(file)) return tracks;
  const num = (value: string | undefined): number | null => {
    const parsed = value === undefined || value === "" ? Number.NaN : Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  for (const r of readCsv(file)) {
    const fund = r.fund ?? "";
    const point: TrackPoint = {
      quarter: r.quarter ?? "",
      fundReturn: num(r.fund_return) ?? 0,
      indexReturn: num(r.benchmark_return),
      fundCum: num(r.fund_cum_return) ?? 0,
      indexCum: num(r.benchmark_cum_return),
    };
    tracks.set(fund, [...(tracks.get(fund) ?? []), point]);
  }
  for (const points of tracks.values()) points.sort((a, b) => a.quarter.localeCompare(b.quarter));
  return tracks;
}

/** Bulleted links to entity pages, for the crawlable /stocks and /funds hubs. */
function directory(heading: string, pages: readonly PublicPage[]): string {
  const items = pages
    .map(
      (p) => `<li><a href="${escapeAttr(canonicalUrl(p.path))}">${escapeHtml(p.heading)}</a></li>`,
    )
    .join("");
  return `<h2>${escapeHtml(heading)}</h2><ul>${items}</ul>`;
}

/**
 * Pre-renders every public route for crawlers that don't run JavaScript: one
 * flat HTML file per route with its own head (title, description, canonical,
 * Open Graph, JSON-LD) and a static body the SPA replaces on mount — the full
 * Q&A on /learn. Then emits sitemap.xml (only URLs that were written, dated from
 * the data) and robots.txt. Enabled only for the public gh-pages build.
 */
function staticSeo(enabled: boolean): Plugin {
  return {
    name: "static-seo",
    apply: "build",
    // writeBundle (not closeBundle): with rolldown-vite the bundle is not yet
    // flushed to disk when closeBundle fires, so dist/index.html would ENOENT.
    writeBundle() {
      if (!enabled) return;
      const distDir = path.resolve(import.meta.dirname, "dist");
      const template = readFileSync(path.resolve(distDir, "index.html"), "utf-8");
      const write = (page: PublicPage, html: string): void => {
        const file = path.resolve(distDir, staticFileFor(page.path));
        mkdirSync(path.dirname(file), { recursive: true });
        writeFileSync(file, html);
      };

      const data = loadLatestQuarter();
      const stockPages: PublicPage[] = [];
      const fundPages: PublicPage[] = [];
      if (data) {
        const summaries = [...buildStockSummaries(data.rows, data.companies).values()].sort(
          (a, b) => b.holders.length - a.holders.length || b.totalValue - a.totalValue,
        );
        const funds = buildFundSummaries(data.rows, data.funds);
        const tracks = loadFundTracks();
        const linkedStocks = new Set<string>();
        for (const summary of summaries) {
          const page = stockEntityPage(summary);
          if (!page) continue;
          stockPages.push(page);
          linkedStocks.add(summary.ticker);
          const html = renderStaticPage({
            template,
            page,
            bodyHtml: renderStockBody(summary, {
              quarter: data.quarter,
              trackedFunds: funds.length,
            }),
            jsonLd: [
              buildBreadcrumbJsonLd([
                { name: "Home", path: ROUTES.home },
                { name: STOCKS_PAGE.heading, path: ROUTES.stocks },
                { name: summary.ticker, path: page.path },
              ]),
            ],
          });
          write(page, html);
        }
        for (const summary of funds) {
          const page = fundEntityPage(summary);
          fundPages.push(page);
          const html = renderStaticPage({
            template,
            page,
            bodyHtml: renderFundBody(summary, {
              quarter: data.quarter,
              stockPages: linkedStocks,
              track: tracks.get(summary.fund),
            }),
            jsonLd: [
              buildBreadcrumbJsonLd([
                { name: "Home", path: ROUTES.home },
                { name: FUNDS_PAGE.heading, path: ROUTES.funds },
                { name: page.heading, path: page.path },
              ]),
            ],
          });
          write(page, html);
        }
      }

      const render = (page: PublicPage): string => {
        if (page === ABOUT_PAGE) {
          return renderStaticPage({
            template,
            page,
            bodyHtml: renderAboutBody(),
            jsonLd: [
              buildBreadcrumbJsonLd([
                { name: "Home", path: ROUTES.home },
                { name: "About", path: ROUTES.about },
              ]),
            ],
          });
        }
        if (page === LEARN_PAGE) {
          return renderFaqStaticHtml({
            template,
            canonical: canonicalUrl(ROUTES.learn),
            meta: FAQ_META,
            sections: FAQ_SECTIONS,
            jsonLd: [
              buildFaqJsonLd(FAQ_SECTIONS),
              buildBreadcrumbJsonLd([
                { name: "Home", path: ROUTES.home },
                { name: "FAQ", path: ROUTES.learn },
              ]),
            ],
          });
        }
        const jsonLd =
          page === HOME_PAGE
            ? [buildHomeJsonLd()]
            : [
                buildBreadcrumbJsonLd([
                  { name: "Home", path: ROUTES.home },
                  { name: page.heading, path: page.path },
                ]),
              ];
        const extra =
          page === STOCKS_PAGE && stockPages.length > 0
            ? directory("Most widely held stocks", stockPages)
            : page === FUNDS_PAGE && fundPages.length > 0
              ? directory("Tracked hedge funds", fundPages)
              : "";
        return renderStaticPage({
          template,
          page,
          bodyHtml: renderPageBody(page, PUBLIC_PAGES, extra),
          jsonLd,
        });
      };
      for (const page of PUBLIC_PAGES) {
        write(page, render(page));
      }

      const filingsDate = databaseDate("non_quarterly.csv", "Filing_Date");
      const backtestDate = databaseDate("performance.csv", "exit_date");
      const lastmodFor = (page: PublicPage): string | null => {
        if (page === LEARN_PAGE) return FAQ_LAST_UPDATED;
        if (page === ABOUT_PAGE) return ABOUT_LAST_UPDATED;
        if (page === PERFORMANCE_PAGE) return backtestDate;
        return filingsDate;
      };
      writeFileSync(
        path.resolve(distDir, "sitemap.xml"),
        buildSitemap(
          [...PUBLIC_PAGES, ...fundPages, ...stockPages].map((page) => ({
            page,
            lastmod: lastmodFor(page),
          })),
          (file) => existsSync(path.resolve(distDir, file)),
        ),
      );

      const robots = [
        "User-agent: *",
        "Allow: /",
        "",
        "# AI search crawlers explicitly welcomed",
        "User-agent: GPTBot",
        "Allow: /",
        "",
        "User-agent: OAI-SearchBot",
        "Allow: /",
        "",
        "User-agent: ClaudeBot",
        "Allow: /",
        "",
        "User-agent: PerplexityBot",
        "Allow: /",
        "",
        `Sitemap: ${SITE_ORIGIN}${SITE_BASE}/sitemap.xml`,
        "",
      ].join("\n");
      writeFileSync(path.resolve(distDir, "robots.txt"), robots);
    },
  };
}

export default defineConfig(({ mode }) => ({
  base: mode === "gh-pages" ? "/hedge-fund-tracker/" : "/",
  define: {
    __GH_PAGES_MODE__: mode === "gh-pages",
    __APP_VERSION__: JSON.stringify(APP_VERSION),
  },
  server: {
    host: "::",
    port: 8080,
    hmr: { overlay: false },
    // Proxy backend routes to the FastAPI process. Run `pipenv run app` on 8000
    // and `npm run dev` here — edits in src/ hot-reload instantly while the
    // backend (CSV serving, /api/*, SSE) stays untouched.
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/database": { target: "http://localhost:8000", changeOrigin: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  publicDir: "public",
  plugins: [react(), staticSeo(mode === "gh-pages")],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (!id.includes("node_modules")) return;
          // Left to the bundler so charts ship with the lazy pages that draw them; a
          // forced chunk also captured React's CJS wrappers and got preloaded everywhere.
          if (id.includes("recharts") || id.includes("d3-") || id.includes("victory-vendor")) {
            return;
          }
          if (id.includes("@tanstack")) return "query";
          if (id.includes("react-router") || id.includes("/react-dom/") || id.includes("/react/")) {
            return "react-vendor";
          }
          if (id.includes("@radix-ui")) return "radix";
          return "vendor";
        },
      },
    },
  },
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "./src") },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/lib/__tests__/**",
        "src/test/**",
        "src/vite-env.d.ts",
      ],
      reporter: ["text-summary", "html"],
    },
  },
}));
