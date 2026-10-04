import { describe, expect, it } from "vitest";

import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  buildHomeJsonLd,
  buildSitemap,
  canonicalUrl,
  latestCsvDate,
  renderFaqStaticHtml,
  renderPageBody,
  renderStaticPage,
  SITE_ORIGIN,
  staticFileFor,
} from "../seo";
import { FAQ_LAST_UPDATED, FAQ_META, FAQ_SECTIONS } from "../faqContent";
import { HOME_PAGE, LATEST_PAGE, LEARN_PAGE, PUBLIC_PAGES } from "../pageMeta";

const TEMPLATE = [
  "<!doctype html>",
  "<html><head>",
  "<title>Hedge Fund Tracker</title>",
  '<meta name="description" content="old" />',
  '<meta property="og:title" content="Generic" />',
  '<meta property="og:description" content="Generic description" />',
  '<meta property="og:type" content="website" />',
  "</head>",
  '<body><div id="root"></div></body>',
  "</html>",
].join("\n");

describe("staticFileFor", () => {
  it("maps home to index.html", () => {
    expect(staticFileFor("/")).toBe("index.html");
  });

  // A flat file is served at the extensionless URL with a 200; a folder
  // index would 301 to a trailing slash and split the canonical.
  it("maps a route to a flat .html file", () => {
    expect(staticFileFor("/latest")).toBe("latest.html");
    expect(staticFileFor("/learn")).toBe("learn.html");
  });

  // The host decodes the request path before looking the file up.
  it("decodes an encoded path into the on-disk file name", () => {
    expect(staticFileFor("/funds/Spruce%20House")).toBe("funds/Spruce House.html");
    expect(staticFileFor("/stock/AMZN")).toBe("stock/AMZN.html");
  });
});

describe("renderStaticPage", () => {
  const html = renderStaticPage({
    template: TEMPLATE,
    page: LATEST_PAGE,
    bodyHtml: "<main><h1>Latest Filings</h1></main>",
    jsonLd: [{ "@type": "Thing", name: "</script><script>alert(1)</script>" }],
  });

  it("sets title, description and a self-referencing canonical", () => {
    expect(html).toContain("<title>Latest Filings — Hedge Fund Tracker</title>");
    expect(html).toContain(`content="${LATEST_PAGE.description}"`);
    expect(html).not.toContain('content="old"');
    expect(html).toContain(`<link rel="canonical" href="${canonicalUrl("/latest")}" />`);
  });

  it("replaces the template's Open Graph tags instead of duplicating them", () => {
    expect(html.match(/property="og:title"/g)).toHaveLength(1);
    expect(html.match(/property="og:description"/g)).toHaveLength(1);
    expect(html.match(/property="og:type"/g)).toHaveLength(1);
    expect(html).not.toContain("Generic");
    expect(html).toContain(`<meta property="og:url" content="${canonicalUrl("/latest")}" />`);
  });

  it("adds a share image and a Twitter card", () => {
    expect(html).toContain(`<meta property="og:image" content="${canonicalUrl("/logo.png")}" />`);
    expect(html).toContain('<meta name="twitter:card" content="summary" />');
  });

  it("escapes < inside JSON-LD so a value cannot close the script tag", () => {
    expect(html).not.toContain("</script><script>alert(1)");
    expect(html).toContain("\\u003c/script>");
  });

  it("injects the body into the SPA root", () => {
    expect(html).toContain('<div id="root"><main><h1>Latest Filings</h1></main></div>');
  });
});

describe("renderPageBody", () => {
  const body = renderPageBody(LATEST_PAGE, PUBLIC_PAGES);

  it("renders the heading and the description", () => {
    expect(body).toContain("<h1>Latest Filings</h1>");
    expect(body).toContain(LATEST_PAGE.description);
  });

  it("links every other public page by its absolute URL", () => {
    for (const page of PUBLIC_PAGES.filter((p) => p !== LATEST_PAGE)) {
      expect(body).toContain(`href="${canonicalUrl(page.path)}"`);
    }
    expect(body).not.toContain(`href="${canonicalUrl("/latest")}"`);
  });

  it("states the data source and that it is not investment advice", () => {
    expect(body).toContain("SEC EDGAR");
    expect(body).toContain("Not investment advice");
  });

  it("appends extra content, such as a directory of entity pages, before the disclaimer", () => {
    const withDirectory = renderPageBody(LATEST_PAGE, PUBLIC_PAGES, "<ul><li>AAA</li></ul>");
    expect(withDirectory.indexOf("<li>AAA</li>")).toBeGreaterThan(-1);
    expect(withDirectory.indexOf("<li>AAA</li>")).toBeLessThan(
      withDirectory.indexOf("Not investment advice"),
    );
  });
});

describe("buildHomeJsonLd", () => {
  const ld = buildHomeJsonLd();
  const node = (type: string) => ld["@graph"].find((n) => n["@type"] === type);

  it("describes the site, its author, the app and the source code", () => {
    expect(node("WebSite")?.url).toBe(canonicalUrl("/"));
    expect(node("Person")?.url).toBe("https://github.com/dokson");
    expect(node("WebApplication")?.applicationCategory).toBe("FinanceApplication");
    expect(node("SoftwareSourceCode")?.codeRepository).toBe(
      "https://github.com/dokson/hedge-fund-tracker",
    );
  });

  it("keeps codeRepository off the WebApplication node", () => {
    expect(node("WebApplication")).not.toHaveProperty("codeRepository");
  });

  // The code is proprietary: the structured data must not call it open source.
  it("never claims the project is open source", () => {
    expect(JSON.stringify(ld).toLowerCase()).not.toContain("open-source");
    expect(JSON.stringify(ld).toLowerCase()).not.toContain("open source");
  });
});

describe("buildSitemap", () => {
  const entries = [
    { page: HOME_PAGE, lastmod: "2026-09-28" },
    { page: LEARN_PAGE, lastmod: "2026-09-03" },
  ];

  it("lists each page's canonical URL with its lastmod", () => {
    const xml = buildSitemap(entries, () => true);
    expect(xml).toContain(`<loc>${canonicalUrl("/")}</loc>`);
    expect(xml).toContain(
      `<loc>${canonicalUrl("/learn")}</loc>\n    <lastmod>2026-09-03</lastmod>`,
    );
  });

  it("fails the build when a listed page has no generated file", () => {
    expect(() => buildSitemap(entries, (file) => file !== "learn.html")).toThrow(/learn\.html/);
  });
});

describe("latestCsvDate", () => {
  const csv = [
    '"Fund","Date","Filing_Date"',
    '"A","2026-09-24","2026-09-28"',
    '"B","2026-09-30","2026-10-01"',
    '"C","2026-08-01",""',
  ].join("\n");

  it("returns the most recent ISO date in the named column", () => {
    expect(latestCsvDate(csv, "Filing_Date")).toBe("2026-10-01");
  });

  it("returns null when the column is missing", () => {
    expect(latestCsvDate(csv, "Nope")).toBeNull();
  });
});

describe("canonicalUrl", () => {
  it("joins origin, base and path without double slashes", () => {
    expect(canonicalUrl("/learn")).toBe(`${SITE_ORIGIN}/hedge-fund-tracker/learn`);
  });

  it("maps the home path to the base root with a trailing slash", () => {
    expect(canonicalUrl("/")).toBe(`${SITE_ORIGIN}/hedge-fund-tracker/`);
  });

  it("produces absolute https URLs", () => {
    expect(canonicalUrl("/learn")).toMatch(/^https:\/\//);
  });
});

describe("buildBreadcrumbJsonLd", () => {
  it("emits a positioned BreadcrumbList with absolute item URLs", () => {
    const ld = buildBreadcrumbJsonLd([
      { name: "Home", path: "/" },
      { name: "FAQ", path: "/learn" },
    ]) as {
      "@type": string;
      itemListElement: Array<{ position: number; name: string; item: string }>;
    };

    expect(ld["@type"]).toBe("BreadcrumbList");
    expect(ld.itemListElement).toHaveLength(2);
    expect(ld.itemListElement[0]).toMatchObject({ position: 1, name: "Home" });
    expect(ld.itemListElement[1].position).toBe(2);
    expect(ld.itemListElement[1].item).toBe(canonicalUrl("/learn"));
  });
});

describe("buildFaqJsonLd", () => {
  const ld = buildFaqJsonLd(FAQ_SECTIONS) as {
    "@context": string;
    "@type": string;
    dateModified: string;
    mainEntity: Array<{ "@type": string; name: string; acceptedAnswer: { text: string } }>;
  };

  it("is a schema.org FAQPage", () => {
    expect(ld["@context"]).toBe("https://schema.org");
    expect(ld["@type"]).toBe("FAQPage");
  });

  it("carries the last-updated date as metadata only", () => {
    expect(ld.dateModified).toBe(FAQ_LAST_UPDATED);
  });

  it("includes every question with its full answer text", () => {
    const allItems = FAQ_SECTIONS.flatMap((s) => s.items);
    expect(ld.mainEntity).toHaveLength(allItems.length);

    const first = allItems[0];
    const entry = ld.mainEntity.find((q) => q.name === first.question);
    expect(entry).toBeDefined();
    expect(entry?.["@type"]).toBe("Question");
    // The full answer must be present so AI crawlers can cite it.
    expect(entry?.acceptedAnswer.text).toContain(first.answer[0]);
  });
});

describe("renderFaqStaticHtml", () => {
  const template = [
    "<!doctype html>",
    "<html><head>",
    "<title>Hedge Fund Tracker</title>",
    '<meta name="description" content="old" />',
    "</head>",
    '<body><div id="root"></div></body>',
    "</html>",
  ].join("\n");

  const html = renderFaqStaticHtml({
    template,
    canonical: canonicalUrl("/learn"),
    meta: FAQ_META,
    sections: FAQ_SECTIONS,
    jsonLd: [buildFaqJsonLd(FAQ_SECTIONS), buildBreadcrumbJsonLd([{ name: "Home", path: "/" }])],
  });

  it("sets the SEO title and meta description from FAQ_META", () => {
    // The title carries an ampersand, which must be HTML-escaped in <title>.
    expect(html).toContain("<title>Hedge Fund &amp; SEC Filing FAQ");
    expect(html).toContain(FAQ_META.description);
    expect(html).not.toContain('content="old"');
  });

  it("adds a self-referencing canonical link", () => {
    expect(html).toContain(`<link rel="canonical" href="${canonicalUrl("/learn")}"`);
  });

  it("bakes the JSON-LD into the head as application/ld+json", () => {
    expect(html).toContain('<script type="application/ld+json">');
    expect(html).toContain('"@type":"FAQPage"');
    expect(html).toContain('"@type":"BreadcrumbList"');
  });

  it("does not duplicate the template's Open Graph tags", () => {
    const withOg = renderFaqStaticHtml({
      template: TEMPLATE,
      canonical: canonicalUrl("/learn"),
      meta: FAQ_META,
      sections: FAQ_SECTIONS,
      jsonLd: [],
    });
    expect(withOg.match(/property="og:title"/g)).toHaveLength(1);
    expect(withOg).not.toContain("Generic");
  });

  it("renders an H1 and every question + answer into #root for no-JS crawlers", () => {
    expect(html).toContain("<h1>Hedge Fund &amp; SEC Filing FAQ</h1>");
    const allItems = FAQ_SECTIONS.flatMap((s) => s.items);
    for (const item of allItems) {
      expect(html).toContain(item.question);
      expect(html).toContain(item.answer[0]);
    }
    // Content lands inside the SPA root so it shows before hydration.
    expect(html).not.toContain('<div id="root"></div>');
  });
});
