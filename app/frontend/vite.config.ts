// vitest/config wraps Vite's defineConfig with the `test` key typed
// deliberately (not via incidental module augmentation).
import { defineConfig } from "vitest/config";
import type { Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { mkdirSync, readFileSync, writeFileSync } from "fs";

import { ROUTES } from "./src/lib/routes";
import { FAQ_LAST_UPDATED, FAQ_META, FAQ_SECTIONS } from "./src/lib/faqContent";
import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  canonicalUrl,
  renderFaqStaticHtml,
  SITE_BASE,
  SITE_ORIGIN,
} from "./src/lib/seo";

// Single source-of-truth for the app version: app/frontend/package.json. The
// backend reads the same field at request time (see app/utils/version.py) so
// every surface (sidebar footer, server /health, GH release tag) agrees.
const pkg: unknown = JSON.parse(readFileSync(path.resolve(__dirname, "package.json"), "utf-8"));
if (
  typeof pkg !== "object" ||
  pkg === null ||
  !("version" in pkg) ||
  typeof pkg.version !== "string"
) {
  throw new Error("package.json is missing a string `version` field");
}
const APP_VERSION: string = pkg.version;

// Public routes worth advertising in the sitemap (excludes parametrised and
// backend-only pages).
const SITEMAP_ROUTES = [
  ROUTES.home,
  ROUTES.latest,
  ROUTES.quarterly,
  ROUTES.strategyPerformance,
  ROUTES.funds,
  ROUTES.stocks,
  ROUTES.learn,
];

/**
 * Bakes a crawler-facing static snapshot of the /learn FAQ (full Q&A + JSON-LD
 * in the HTML, so AI/search crawlers that don't run JavaScript read it) and
 * emits sitemap.xml + robots.txt. Enabled only for the public gh-pages build.
 */
function faqStaticSeo(enabled: boolean): Plugin {
  return {
    name: "faq-static-seo",
    apply: "build",
    closeBundle() {
      if (!enabled) return;
      const distDir = path.resolve(__dirname, "dist");
      const template = readFileSync(path.resolve(distDir, "index.html"), "utf-8");

      const html = renderFaqStaticHtml({
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
      mkdirSync(path.resolve(distDir, "learn"), { recursive: true });
      writeFileSync(path.resolve(distDir, "learn/index.html"), html);

      const urls = SITEMAP_ROUTES.map((route) => {
        const lastmod =
          route === ROUTES.learn ? `\n    <lastmod>${FAQ_LAST_UPDATED}</lastmod>` : "";
        return `  <url>\n    <loc>${canonicalUrl(route)}</loc>${lastmod}\n  </url>`;
      }).join("\n");
      writeFileSync(
        path.resolve(distDir, "sitemap.xml"),
        `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`,
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
  plugins: [react(), faqStaticSeo(mode === "gh-pages")],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (!id.includes("node_modules")) return;
          if (id.includes("recharts") || id.includes("d3-")) return "charts";
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
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
}));
