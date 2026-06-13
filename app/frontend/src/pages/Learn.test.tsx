/**
 * Tests for the /learn FAQ page: it renders the heading, breadcrumb and every
 * question, and wires per-route SEO metadata (title + FAQPage JSON-LD) through
 * usePageMeta.
 */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import Learn from "./Learn";
import { FAQ_META, FAQ_SECTIONS } from "@/lib/faqContent";

function renderLearn() {
  return render(
    <MemoryRouter initialEntries={["/learn"]}>
      <Learn />
    </MemoryRouter>,
  );
}

describe("Learn page", () => {
  it("renders the H1 heading and intro", () => {
    const { getByRole, getByText } = renderLearn();
    expect(getByRole("heading", { level: 1 }).textContent).toContain(FAQ_META.heading);
    expect(getByText(FAQ_META.intro)).toBeDefined();
  });

  it("renders a heading for every section", () => {
    const { getAllByRole } = renderLearn();
    const headingTexts = getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    for (const section of FAQ_SECTIONS) {
      expect(headingTexts).toContain(section.title);
    }
  });

  it("renders every question as an accordion trigger", () => {
    const { getByText } = renderLearn();
    for (const item of FAQ_SECTIONS.flatMap((s) => s.items)) {
      expect(getByText(item.question)).toBeDefined();
    }
  });

  it("sets the document title from FAQ_META", () => {
    renderLearn();
    expect(document.title).toBe(FAQ_META.title);
  });

  it("injects FAQPage JSON-LD into the document head", () => {
    renderLearn();
    const scripts = Array.from(
      document.head.querySelectorAll<HTMLScriptElement>(
        'script[type="application/ld+json"][data-managed="page-meta"]',
      ),
    );
    const combined = scripts.map((s) => s.text).join("");
    expect(combined).toContain('"@type":"FAQPage"');
    expect(combined).toContain('"@type":"BreadcrumbList"');
  });
});
