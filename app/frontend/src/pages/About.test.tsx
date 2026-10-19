import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import About from "./About";

function renderAbout() {
  return render(
    <MemoryRouter initialEntries={["/about"]}>
      <About />
    </MemoryRouter>,
  );
}

describe("About page", () => {
  it("keeps FAQ links in-app and opens external ones in a new tab", () => {
    renderAbout();
    const faq = screen.getByRole("link", { name: "how the tracked funds are selected" });
    expect(faq.getAttribute("href")).toBe("/learn#how-funds-are-selected");
    const coalesce = screen.getByRole("link", { name: "COalesCE" });
    expect(coalesce.getAttribute("href")).toBe("https://www.coalesce.coach/en");
    expect(coalesce.getAttribute("target")).toBe("_blank");
    expect(coalesce.getAttribute("rel")).toContain("noopener");
  });
});
