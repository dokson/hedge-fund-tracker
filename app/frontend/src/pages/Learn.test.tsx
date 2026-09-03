/**
 * Tests for the /learn FAQ page: it renders the heading, breadcrumb and every
 * question, and wires per-route SEO metadata (title + FAQPage JSON-LD) through
 * usePageMeta.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import Learn from "./Learn";
import { FAQ_META, FAQ_SECTIONS } from "@/lib/faqContent";

function renderLearn(entry = "/learn") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Learn />
    </MemoryRouter>,
  );
}

// jsdom implements no scrolling at all, so scrollIntoView has to be stubbed
// before it can be observed.
const scrollIntoView = vi.fn<(options?: boolean | ScrollIntoViewOptions) => void>();

describe("Learn page", () => {
  beforeEach(() => {
    scrollIntoView.mockClear();
    Element.prototype.scrollIntoView = scrollIntoView;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

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

  it("opens the accordion item named by the URL hash", async () => {
    const { getByRole } = renderLearn("/learn#how-funds-are-selected");
    const trigger = getByRole("button", { name: /How are the tracked funds selected/ });
    expect(trigger.id).toBe("how-funds-are-selected");
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    // Keyboard/screen-reader users land on the question itself. The scroll and
    // focus are deferred by a frame, so this settles asynchronously.
    await waitFor(() => expect(document.activeElement).toBe(trigger));
  });

  // The deep-link scroll used to be issued in the same tick as the open state
  // and never landed on a cold load; it now runs after a painted frame.
  it("scrolls the hash-named trigger into view", async () => {
    const { getByRole } = renderLearn("/learn#how-funds-are-selected");
    const trigger = getByRole("button", { name: /How are the tracked funds selected/ });
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalled());
    expect(scrollIntoView.mock.instances).toContain(trigger);
    expect(scrollIntoView.mock.calls[0]?.[0]).toMatchObject({ block: "start" });
  });

  it("leaves every item closed without a hash", () => {
    const { getByRole } = renderLearn();
    const trigger = getByRole("button", { name: /How are the tracked funds selected/ });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
  });
});
