/**
 * SEO/GEO helpers shared by the live page and the build-time static
 * pre-renderer. Kept free of React and browser globals (no `window`) so the
 * gh-pages Vite plugin can import it in a Node context.
 *
 * The canonical public origin lives here as a single constant: switching from
 * the GitHub Pages URL to a custom domain is a one/two-line change (set
 * SITE_ORIGIN to the domain and SITE_BASE to "" — keep SITE_BASE in sync with
 * BASE_PATH in config.ts).
 */
import type { FaqSection } from "./faqContent.ts";
import { FAQ_LAST_UPDATED, FAQ_META } from "./faqContent.ts";
import type { PublicPage } from "./pageMeta.ts";
import { SITE_NAME } from "./pageMeta.ts";

/** Canonical site origin (scheme + host), no trailing slash. */
export const SITE_ORIGIN = "https://dokson.github.io";

/** Sub-path the site is served from. Mirror of config.BASE_PATH for gh-pages. */
export const SITE_BASE = "/hedge-fund-tracker";

/**
 * Builds an absolute canonical URL for an in-app route path (e.g. "/learn").
 */
export function canonicalUrl(routePath: string): string {
  const path = routePath === "/" ? "/" : routePath.replace(/\/+$/, "");
  return `${SITE_ORIGIN}${SITE_BASE}${path}`.replace(/([^:])\/{2,}/g, "$1/");
}

/** Escapes the three characters that are unsafe in HTML text nodes. */
export function escapeHtml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Escapes for use inside a double-quoted HTML attribute value. */
export function escapeAttr(value: string): string {
  return escapeHtml(value).replace(/"/g, "&quot;");
}

export interface Crumb {
  name: string;
  /** In-app route path; resolved to an absolute URL in the schema. */
  path: string;
}

/**
 * Builds schema.org BreadcrumbList JSON-LD with absolute item URLs.
 */
export function buildBreadcrumbJsonLd(crumbs: Crumb[]): object {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: crumbs.map((crumb, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: crumb.name,
      item: canonicalUrl(crumb.path),
    })),
  };
}

/**
 * Builds schema.org FAQPage JSON-LD carrying every question and its full
 * answer text. Google retired FAQ rich results in 2026, so this no longer
 * yields a SERP feature — it is kept because the full Q&A text still feeds
 * AI/LLM citation and entity resolution.
 */
export function buildFaqJsonLd(sections: FaqSection[]): object {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    // Freshness signal for AI/search; not rendered visibly (metadata only).
    dateModified: FAQ_LAST_UPDATED,
    mainEntity: sections
      .flatMap((section) => section.items)
      .map((item) => ({
        "@type": "Question",
        name: item.question,
        acceptedAnswer: {
          "@type": "Answer",
          text: item.answer.join(" "),
        },
      })),
  };
}

/** Renders the visible FAQ body as semantic HTML for the static snapshot. */
function renderFaqBody(params: { meta: typeof FAQ_META; sections: FaqSection[] }): string {
  const { meta, sections } = params;

  const body = sections
    .map((section) => {
      const items = section.items
        .map((item) => {
          const paragraphs = item.answer.map((p) => `<p>${escapeHtml(p)}</p>`).join("");
          return `<div><h3 id="${item.id}">${escapeHtml(item.question)}</h3>${paragraphs}</div>`;
        })
        .join("");
      return `<section id="${section.id}"><h2>${escapeHtml(section.title)}</h2>${items}</section>`;
    })
    .join("");

  return [
    "<main>",
    `<h1>${escapeHtml(meta.heading)}</h1>`,
    `<p>${escapeHtml(meta.intro)}</p>`,
    body,
    "</main>",
  ].join("");
}

/**
 * File the static build writes for a route. Flat `<route>.html` rather than
 * `<route>/index.html`: GitHub Pages serves it at the extensionless URL with a
 * 200, while a folder index answers with a 301 to the trailing-slash form.
 */
export function staticFileFor(routePath: string): string {
  if (routePath === "/") return "index.html";
  return `${decodeURIComponent(routePath.replace(/^\/+|\/+$/g, ""))}.html`;
}

/** JSON for an inline <script>: `<` is escaped so a value cannot close the tag. */
function inlineJson(value: object): string {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}

const VISUALLY_HIDDEN =
  "position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0";

/**
 * Turns the built index.html into a crawler-facing document for one route:
 * title, description, canonical, Open Graph (replacing the template's generic
 * pair rather than adding a second one), Twitter card and JSON-LD in <head>, and
 * the static body inside the SPA root so it reads without JavaScript.
 */
export function renderStaticPage(params: {
  template: string;
  page: Pick<PublicPage, "path" | "title" | "description">;
  bodyHtml: string;
  jsonLd: object[];
  canonical?: string;
}): string {
  const { template, page, bodyHtml, jsonLd } = params;
  const canonical = params.canonical ?? canonicalUrl(page.path);

  const headTags = [
    `<link rel="canonical" href="${escapeAttr(canonical)}" />`,
    `<meta property="og:title" content="${escapeAttr(page.title)}" />`,
    `<meta property="og:description" content="${escapeAttr(page.description)}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:url" content="${escapeAttr(canonical)}" />`,
    `<meta property="og:site_name" content="${escapeAttr(SITE_NAME)}" />`,
    `<meta property="og:image" content="${escapeAttr(canonicalUrl("/logo.png"))}" />`,
    `<meta name="twitter:card" content="summary" />`,
    ...jsonLd.map((ld) => `<script type="application/ld+json">${inlineJson(ld)}</script>`),
  ].join("\n    ");

  return template
    .replace(/\s*<meta\s+property="og:[^"]*"[^>]*>/g, "")
    .replace(/<title>[\s\S]*?<\/title>/, `<title>${escapeHtml(page.title)}</title>`)
    .replace(
      /<meta\s+name="description"[\s\S]*?\/?>/,
      `<meta name="description" content="${escapeAttr(page.description)}" />`,
    )
    .replace(/<\/head>/, `    ${headTags}\n  </head>`)
    .replace(
      /<div id="root">\s*<\/div>/,
      `<div id="root"><div style="${VISUALLY_HIDDEN}">${bodyHtml}</div></div>`,
    );
}

/**
 * Static body for a public page: its heading and summary, links to every other
 * public page (crawlable internal linking) and the data-source disclaimer.
 */
export function renderPageBody(
  page: PublicPage,
  pages: readonly PublicPage[],
  extraHtml = "",
): string {
  const links = pages
    .filter((other) => other.path !== page.path)
    .map(
      (other) =>
        `<li><a href="${escapeAttr(canonicalUrl(other.path))}">${escapeHtml(other.heading)}</a></li>`,
    )
    .join("");
  return [
    "<main>",
    `<h1>${escapeHtml(page.heading)}</h1>`,
    `<p>${escapeHtml(page.description)}</p>`,
    `<nav aria-label="${escapeAttr(SITE_NAME)}"><ul>${links}</ul></nav>`,
    extraHtml,
    "<p>Data from SEC EDGAR filings (13F, 13D/G, Form 4). Not investment advice.</p>",
    "</main>",
  ].join("");
}

const AUTHOR_ID = `${canonicalUrl("/")}#author`;
const APP_ID = `${canonicalUrl("/")}#app`;

export interface JsonLdGraph {
  "@context": "https://schema.org";
  "@graph": Array<Record<string, unknown>>;
}

/**
 * Home-page entity graph: the site, its author, the web app and its source
 * repository. The repository is a separate SoftwareSourceCode node because
 * `codeRepository` is not a WebApplication property, and nothing here calls the
 * project open source: the code is proprietary.
 */
export function buildHomeJsonLd(): JsonLdGraph {
  const home = canonicalUrl("/");
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite",
        "@id": `${home}#website`,
        url: home,
        name: SITE_NAME,
        description:
          "Free tracker of hedge fund SEC filings (13F, 13D/G, Form 4) with consensus stock signals.",
        inLanguage: "en",
        publisher: { "@id": AUTHOR_ID },
      },
      {
        "@type": "Person",
        "@id": AUTHOR_ID,
        name: "Alessandro Colace",
        url: "https://github.com/dokson",
        sameAs: ["https://github.com/dokson"],
      },
      {
        "@type": "WebApplication",
        "@id": APP_ID,
        name: SITE_NAME,
        url: home,
        applicationCategory: "FinanceApplication",
        operatingSystem: "Any (web browser)",
        browserRequirements: "Requires JavaScript",
        isAccessibleForFree: true,
        image: canonicalUrl("/logo.png"),
        description:
          "Merges quarterly 13F filings with 13D/G and Form 4 activity to show what hedge funds are buying and selling.",
        offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
        author: { "@id": AUTHOR_ID },
      },
      {
        "@type": "SoftwareSourceCode",
        "@id": `${home}#source`,
        name: `${SITE_NAME} source code`,
        codeRepository: "https://github.com/dokson/hedge-fund-tracker",
        programmingLanguage: ["Python", "TypeScript"],
        author: { "@id": AUTHOR_ID },
        targetProduct: { "@id": APP_ID },
      },
    ],
  };
}

export interface SitemapEntry {
  page: Pick<PublicPage, "path">;
  lastmod: string | null;
}

/**
 * Builds sitemap.xml and refuses to list a URL the build did not write: a
 * sitemap entry that serves the SPA's 404 fallback is reported as an error.
 */
export function buildSitemap(
  entries: readonly SitemapEntry[],
  fileExists: (file: string) => boolean,
): string {
  const missing = entries
    .map(({ page }) => staticFileFor(page.path))
    .filter((file) => !fileExists(file));
  if (missing.length > 0) {
    throw new Error(`sitemap lists pages with no generated file: ${missing.join(", ")}`);
  }
  const urls = entries
    .map(({ page, lastmod }) => {
      const mod = lastmod ? `\n    <lastmod>${lastmod}</lastmod>` : "";
      return `  <url>\n    <loc>${canonicalUrl(page.path)}</loc>${mod}\n  </url>`;
    })
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
}

/** Most recent ISO date (YYYY-MM-DD) in a quoted CSV column, or null. */
export function latestCsvDate(csv: string, column: string): string | null {
  const [header, ...rows] = csv.split(/\r?\n/).filter((line) => line.trim() !== "");
  const index = (header ?? "")
    .split(",")
    .map((h) => h.replace(/"/g, ""))
    .indexOf(column);
  if (index < 0) return null;
  let latest: string | null = null;
  for (const row of rows) {
    const value = (row.split(",")[index] ?? "").replace(/"/g, "");
    if (/^\d{4}-\d{2}-\d{2}$/.test(value) && (latest === null || value > latest)) latest = value;
  }
  return latest;
}

/**
 * Produces a fully static /learn HTML document: the shared static-page head plus
 * the full Q&A in the SPA root, so crawlers that do not run JavaScript read it.
 */
export function renderFaqStaticHtml(params: {
  template: string;
  canonical: string;
  meta: typeof FAQ_META;
  sections: FaqSection[];
  jsonLd: object[];
}): string {
  const { template, canonical, meta, sections, jsonLd } = params;
  return renderStaticPage({
    template,
    canonical,
    page: { path: "/learn", title: meta.title, description: meta.description },
    bodyHtml: renderFaqBody({ meta, sections }),
    jsonLd,
  });
}
