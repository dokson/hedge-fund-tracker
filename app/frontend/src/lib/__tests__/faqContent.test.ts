import { describe, expect, it } from "vitest";

import { FAQ_LAST_UPDATED, FAQ_META, FAQ_SECTIONS } from "../faqContent";

describe("FAQ content", () => {
  const allItems = FAQ_SECTIONS.flatMap((s) => s.items);

  it("has at least one section, each with at least one item", () => {
    expect(FAQ_SECTIONS.length).toBeGreaterThan(0);
    for (const section of FAQ_SECTIONS) {
      expect(section.items.length).toBeGreaterThan(0);
    }
  });

  it("uses unique ids across sections and items", () => {
    const sectionIds = FAQ_SECTIONS.map((s) => s.id);
    expect(new Set(sectionIds).size).toBe(sectionIds.length);

    const itemIds = allItems.map((i) => i.id);
    expect(new Set(itemIds).size).toBe(itemIds.length);
  });

  it("has non-empty, kebab-case ids and non-empty Q&A text", () => {
    for (const section of FAQ_SECTIONS) {
      expect(section.id).toMatch(/^[a-z0-9-]+$/);
      expect(section.title.trim()).not.toBe("");
      for (const item of section.items) {
        expect(item.id).toMatch(/^[a-z0-9-]+$/);
        expect(item.question.trim()).not.toBe("");
        expect(item.answer.length).toBeGreaterThan(0);
        for (const paragraph of item.answer) {
          expect(paragraph.trim()).not.toBe("");
        }
      }
    }
  });

  it("exposes page metadata within SEO length budgets", () => {
    expect(FAQ_META.title.length).toBeLessThanOrEqual(60);
    expect(FAQ_META.description.length).toBeGreaterThanOrEqual(110);
    expect(FAQ_META.description.length).toBeLessThanOrEqual(165);
    expect(FAQ_META.heading.trim()).not.toBe("");
  });

  it("has an ISO-8601 last-updated date", () => {
    expect(FAQ_LAST_UPDATED).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
