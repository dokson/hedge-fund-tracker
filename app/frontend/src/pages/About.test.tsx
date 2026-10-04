import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { ABOUT_HEADING, ABOUT_SECTIONS } from "@/lib/aboutContent";
import { ABOUT_PAGE } from "@/lib/pageMeta";
import About from "./About";

function renderAbout() {
  return render(
    <MemoryRouter initialEntries={["/about"]}>
      <About />
    </MemoryRouter>,
  );
}

describe("About page", () => {
  it("renders the heading and every section", () => {
    renderAbout();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(ABOUT_HEADING);
    for (const section of ABOUT_SECTIONS) {
      expect(screen.getByRole("heading", { level: 2, name: section.title })).toBeTruthy();
    }
  });

  it("keeps FAQ links in-app and opens external ones in a new tab", () => {
    renderAbout();
    const faq = screen.getByRole("link", { name: "how the tracked funds are selected" });
    expect(faq.getAttribute("href")).toBe("/learn#how-funds-are-selected");
    const coalesce = screen.getByRole("link", { name: "COalesCE" });
    expect(coalesce.getAttribute("href")).toBe("https://www.coalesce.coach/en");
    expect(coalesce.getAttribute("target")).toBe("_blank");
    expect(coalesce.getAttribute("rel")).toContain("noopener");
  });

  it("sets the page title", () => {
    renderAbout();
    expect(document.title).toBe(ABOUT_PAGE.title);
  });
});
