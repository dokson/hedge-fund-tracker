/**
 * Tests for the /learn FAQ page: it renders every question, tracks the active
 * section on scroll and opens/scrolls to the item named by the URL hash.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import Learn from "./Learn";
import { FAQ_SECTIONS } from "@/lib/faqContent";

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

  it("renders every question as an accordion trigger", () => {
    const { getByText } = renderLearn();
    for (const item of FAQ_SECTIONS.flatMap((s) => s.items)) {
      expect(getByText(item.question)).toBeDefined();
    }
  });

  it("tracks the active section on window scroll when no container scrolls", async () => {
    const { getAllByRole } = renderLearn();
    const second = FAQ_SECTIONS[1];
    const secondHeading = getAllByRole("heading", { level: 2 }).find(
      (h) => h.textContent === second.title,
    );
    const section = secondHeading?.closest("section") ?? secondHeading?.parentElement;
    expect(section).toBeTruthy();
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (
      this: Element,
    ) {
      return new DOMRect(0, this === section ? 10 : 2000, 0, 0);
    });

    window.dispatchEvent(new Event("scroll"));

    await waitFor(() => {
      const current = document.querySelector('[aria-current="location"]');
      expect(current?.textContent).toContain(second.title);
    });
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
