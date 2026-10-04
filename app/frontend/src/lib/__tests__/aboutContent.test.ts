import { describe, expect, it } from "vitest";

import { ABOUT_SECTIONS, renderAboutBody, type Segment } from "../aboutContent";
import { FAQ_SECTIONS } from "../faqContent";
import { ABOUT_PAGE, PUBLIC_PAGES } from "../pageMeta";
import { canonicalUrl } from "../seo";

const links = ABOUT_SECTIONS.flatMap((s) => s.paragraphs.flat()).filter(
  (seg): seg is Exclude<Segment, string> => typeof seg !== "string",
);

describe("about content", () => {
  it("is a public, pre-rendered page", () => {
    expect(PUBLIC_PAGES).toContain(ABOUT_PAGE);
    expect(ABOUT_PAGE.path).toBe("/about");
  });

  it("credits COalesCE and points corrections to GitHub issues", () => {
    const hrefs = links.map((l) => l.href);
    expect(hrefs).toContain("https://www.coalesce.coach/en");
    expect(hrefs).toContain("https://github.com/dokson/hedge-fund-tracker/issues");
  });

  it("only links FAQ answers that exist", () => {
    const faqIds = new Set(FAQ_SECTIONS.flatMap((s) => s.items.map((i) => i.id)));
    const anchors = links
      .map((l) => l.href)
      .filter((href) => href.startsWith("/learn#"))
      .map((href) => href.slice("/learn#".length));
    expect(anchors.length).toBeGreaterThan(0);
    for (const id of anchors) expect(faqIds).toContain(id);
  });

  // The code is proprietary (All Rights Reserved): source-available, not open source.
  it("never calls the project open source", () => {
    const text = JSON.stringify(ABOUT_SECTIONS).toLowerCase();
    expect(text).not.toContain("open source");
    expect(text).not.toContain("open-source");
  });

  // Publication is a manual merge, so no schedule or turnaround is promised.
  it("promises no update cadence or correction turnaround", () => {
    const text = JSON.stringify(ABOUT_SECTIONS).toLowerCase();
    expect(text).not.toContain("several times");
    expect(text).not.toContain("each weekday");
    expect(text).not.toContain("usually shipped");
    expect(text).toContain("published after review");
  });

  it("states that the roster is pre-selected on past performance", () => {
    expect(JSON.stringify(ABOUT_SECTIONS)).toContain("pre-selected on past performance");
  });

  it("separates what funds report from what the tool computes", () => {
    expect(ABOUT_SECTIONS.map((s) => s.id)).toEqual(
      expect.arrayContaining(["roster", "reported-vs-computed", "privacy"]),
    );
  });

  it("licenses the data CC BY-NC 4.0 and links the licence text", () => {
    expect(JSON.stringify(ABOUT_SECTIONS)).toContain("CC BY-NC 4.0");
    expect(links.map((l) => l.href)).toContain(
      "https://github.com/dokson/hedge-fund-tracker/blob/master/LICENSE-DATA",
    );
  });

  // Owner-confirmed 2026-10-03: no ties to tracked funds, no paid placement, may hold positions.
  it("declares independence and the possibility of personal positions", () => {
    const independence = ABOUT_SECTIONS.find((s) => s.id === "independence");
    const text = JSON.stringify(independence);
    expect(text).toContain("no commercial relationship with the funds it tracks");
    expect(text).toContain("no fund can pay to be included");
    expect(text).toContain("may hold positions");
  });

  it("carries a full not-investment-advice disclaimer", () => {
    expect(JSON.stringify(ABOUT_SECTIONS)).toContain("not investment advice");
  });
});

describe("renderAboutBody", () => {
  const html = renderAboutBody();

  it("renders one H1 and an H2 per section", () => {
    expect(html.match(/<h1>/g)).toHaveLength(1);
    expect(html.match(/<h2>/g)).toHaveLength(ABOUT_SECTIONS.length);
  });

  it("resolves in-app links to absolute URLs and keeps external ones", () => {
    expect(html).toContain(`href="${canonicalUrl("/learn")}#how-funds-are-selected"`);
    expect(html).toContain('href="https://www.coalesce.coach/en"');
  });
});
