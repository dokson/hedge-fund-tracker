import { describe, expect, it } from "vitest";

import {
  buildBreadcrumbJsonLd,
  buildFaqJsonLd,
  canonicalUrl,
  renderFaqStaticHtml,
  SITE_ORIGIN,
} from "../seo";
import { FAQ_LAST_UPDATED, FAQ_META, FAQ_SECTIONS } from "../faqContent";

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

  it("escapes HTML-significant characters in content", () => {
    const ampItem = FAQ_SECTIONS.flatMap((s) => s.items).find((i) => i.question.includes("&"));
    // The page heading contains an ampersand regardless of item content.
    expect(html).toContain("Hedge Fund &amp; SEC Filing FAQ");
    if (ampItem) {
      // oxlint-disable-next-line vitest/no-conditional-expect
      expect(html).not.toContain(ampItem.question); // raw & should be escaped
    }
  });
});
