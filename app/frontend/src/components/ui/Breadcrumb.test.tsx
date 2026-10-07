import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { Breadcrumb } from "./Breadcrumb";

describe("Breadcrumb", () => {
  it("links every ancestor and marks the page itself as current, not as a link", () => {
    render(
      <MemoryRouter>
        <Breadcrumb trail={[{ label: "Stocks", to: "/stocks" }]} current="NVDA" />
      </MemoryRouter>,
    );

    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(nav).getByRole("link", { name: "Stocks" }).getAttribute("href")).toBe("/stocks");
    expect(within(nav).queryByRole("link", { name: "NVDA" })).toBeNull();
    expect(within(nav).getByText("NVDA").getAttribute("aria-current")).toBe("page");
  });
});
