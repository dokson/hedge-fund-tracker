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
import type { FaqSection } from "./faqContent";
import { FAQ_LAST_UPDATED, FAQ_META } from "./faqContent";

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
 * Produces a fully static /learn HTML document from the built index.html
 * template: it rewrites the title and meta description, adds a self-referencing
 * canonical, bakes the JSON-LD into <head>, and injects the rendered Q&A into
 * the SPA root so crawlers (which do not run JavaScript) read the full content.
 */
export function renderFaqStaticHtml(params: {
  template: string;
  canonical: string;
  meta: typeof FAQ_META;
  sections: FaqSection[];
  jsonLd: object[];
}): string {
  const { template, canonical, meta, sections, jsonLd } = params;

  const headTags = [
    `<link rel="canonical" href="${escapeAttr(canonical)}" />`,
    `<meta property="og:title" content="${escapeAttr(meta.title)}" />`,
    `<meta property="og:description" content="${escapeAttr(meta.description)}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:url" content="${escapeAttr(canonical)}" />`,
    ...jsonLd.map((ld) => `<script type="application/ld+json">${JSON.stringify(ld)}</script>`),
  ].join("\n    ");

  let html = template
    .replace(/<title>[\s\S]*?<\/title>/, `<title>${escapeHtml(meta.title)}</title>`)
    .replace(
      /<meta\s+name="description"[\s\S]*?\/?>/,
      `<meta name="description" content="${escapeAttr(meta.description)}" />`,
    )
    .replace(/<\/head>/, `    ${headTags}\n  </head>`);

  const body = renderFaqBody({ meta, sections });
  html = html.replace(/<div id="root">\s*<\/div>/, `<div id="root">${body}</div>`);

  return html;
}
