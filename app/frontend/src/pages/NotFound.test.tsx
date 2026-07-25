/**
 * Tests for the 404 page: it echoes the attempted path, and every escape hatch
 * is a router Link (a raw <a href="/"> would ignore BASE_PATH and leave the app
 * entirely under the GH Pages project path).
 */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import NotFound from "./NotFound";
import { ROUTES } from "@/lib/routes";

function renderNotFound(path = "/no-such-route") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <NotFound />
    </MemoryRouter>,
  );
}

describe("NotFound page", () => {
  it("renders the 404 heading", () => {
    const { getByRole } = renderNotFound();
    expect(getByRole("heading", { level: 1 }).textContent).toContain("404");
  });

  it("echoes the attempted path so the user sees what failed to resolve", () => {
    const { getByText } = renderNotFound("/quarterlyy");
    expect(getByText("/quarterlyy")).toBeDefined();
  });

  it("links home through the router rather than a raw anchor", () => {
    const { getByRole } = renderNotFound();
    const home = getByRole("link", { name: /back to home/i });
    expect(home.getAttribute("href")).toBe(ROUTES.home);
  });

  it("offers router links to the main sections as recovery routes", () => {
    const { getByRole } = renderNotFound();
    for (const path of [ROUTES.latest, ROUTES.quarterly, ROUTES.stocks, ROUTES.funds]) {
      expect(getByRole("link", { name: new RegExp(path.slice(1), "i") })).toBeDefined();
    }
  });

  it("prefixes the router basename on every recovery link", () => {
    const basename = "/hedge-fund-tracker";
    const { getAllByRole } = render(
      <MemoryRouter basename={basename} initialEntries={[`${basename}/no-such-route`]}>
        <NotFound />
      </MemoryRouter>,
    );
    const inAppHrefs = getAllByRole("link")
      .map((a) => a.getAttribute("href") ?? "")
      .filter((href) => href.startsWith("/"));
    expect(inAppHrefs.length).toBeGreaterThan(0);
    for (const href of inAppHrefs) {
      expect(href === basename || href.startsWith(`${basename}/`)).toBe(true);
    }
  });
});
