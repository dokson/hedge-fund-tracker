import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { PageEnd } from "./PageEnd";

const renderEnd = () =>
  render(
    <MemoryRouter>
      <main id="main">
        <PageEnd
          links={[
            { label: "All stocks", to: "/stocks" },
            { label: "Fund ranking", to: "/ranking" },
          ]}
        />
      </main>
    </MemoryRouter>,
  );

describe("PageEnd", () => {
  it("offers the next places to go", () => {
    renderEnd();
    const nav = screen.getByRole("navigation", { name: "Keep exploring" });
    expect(within(nav).getByRole("link", { name: "All stocks" }).getAttribute("href")).toBe(
      "/stocks",
    );
    expect(within(nav).getByRole("link", { name: "Fund ranking" }).getAttribute("href")).toBe(
      "/ranking",
    );
  });

  it("scrolls the page container back to the top", () => {
    renderEnd();
    const main = document.getElementById("main")!;
    main.scrollTop = 800;

    fireEvent.click(screen.getByRole("button", { name: "Back to top" }));

    expect(main.scrollTop).toBe(0);
  });
});
