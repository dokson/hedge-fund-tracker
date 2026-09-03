import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MobileNav } from "./MobileNav";
import { SidebarProvider, useSidebar } from "@/components/ui/sidebar";

vi.mock("@/lib/dataService", () => ({
  getStocks: () => Promise.resolve([]),
  getHedgeFunds: () => Promise.resolve([]),
  getAvailableQuarters: () => Promise.resolve([]),
  getLatestQuarter: () => Promise.resolve("2025Q2"),
}));

/** The header toggle, plus a `#main` for the `inert` check and a second route. */
function Harness() {
  const { toggleSidebar } = useSidebar();
  const navigate = useNavigate();
  return (
    <>
      <button type="button" aria-label="Open navigation" onClick={toggleSidebar}>
        menu
      </button>
      <main id="main">
        <button type="button" onClick={() => navigate("/stocks")}>
          go elsewhere
        </button>
      </main>
    </>
  );
}

function renderNav() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <SidebarProvider>
          <MobileNav />
          <Routes>
            <Route path="*" element={<Harness />} />
          </Routes>
        </SidebarProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function openMenu() {
  const toggle = screen.getByRole("button", { name: "Open navigation" });
  toggle.focus();
  fireEvent.click(toggle);
  return toggle;
}

describe("MobileNav", () => {
  beforeEach(() => {
    // `useIsMobile` reads innerWidth; jsdom defaults to 1024, which would make
    // the overlay close itself as a desktop viewport. jsdom also ships no
    // matchMedia, which the same hook subscribes to.
    window.innerWidth = 390;
    window.matchMedia = ((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    })) as unknown as typeof window.matchMedia;
  });

  it("opens full-screen, moves focus inside and takes the page behind out of play", async () => {
    renderNav();
    openMenu();

    const dialog = await screen.findByRole("dialog", { name: "Navigation" });
    expect(dialog.className).toContain("inset-0");
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Close navigation" }));
    // The search field and the sections are all in the overlay.
    expect(dialog.querySelector("input")).not.toBeNull();
    expect(screen.getByRole("navigation", { name: "Main menu" })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Latest Filings/ })).toBeTruthy();

    const main = document.getElementById("main");
    expect(main?.inert).toBe(true);
  });

  it("closes on Escape and returns focus to the toggle", async () => {
    renderNav();
    const toggle = openMenu();
    await screen.findByRole("dialog", { name: "Navigation" });

    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull();
    });
    await waitFor(() => expect(document.activeElement).toBe(toggle));
    expect(document.getElementById("main")?.inert).toBe(false);
  });

  it("closes on the visible close button", async () => {
    renderNav();
    openMenu();
    await screen.findByRole("dialog", { name: "Navigation" });

    fireEvent.click(screen.getByRole("button", { name: "Close navigation" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull();
    });
  });

  it("closes on a route change with no click of its own (browser back/forward)", async () => {
    renderNav();
    openMenu();
    await screen.findByRole("dialog", { name: "Navigation" });

    // Queried through the DOM: Radix has `aria-hidden` the page behind, so the
    // button is (correctly) out of the accessibility tree while the menu is open.
    const away = document.querySelector<HTMLButtonElement>("#main button");
    fireEvent.click(away!);

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Navigation" })).toBeNull();
    });
  });
});
