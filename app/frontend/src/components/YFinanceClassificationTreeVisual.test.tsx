/**
 * Sector/industry search in the classification tree (shared matchesQuery):
 * case-insensitive, whitespace-tolerant, matching either level.
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import YFinanceClassificationTreeVisual from "./YFinanceClassificationTreeVisual";

import type { getSectorHierarchy as getSectorHierarchyType } from "@/lib/dataService";

vi.mock("@/lib/dataService", () => ({
  getSectorHierarchy: vi.fn<typeof getSectorHierarchyType>(async () => [
    { sector: "Technology", industry: "Semiconductors" },
    { sector: "Technology", industry: "Software—Application" },
    { sector: "Energy", industry: "Oil & Gas Integrated" },
  ]),
}));

async function renderTree() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <YFinanceClassificationTreeVisual />
    </QueryClientProvider>,
  );
  await screen.findByText("Energy");
}

function search(value: string) {
  fireEvent.change(screen.getByLabelText("Search sector or industry"), { target: { value } });
}

describe("YFinanceClassificationTreeVisual search", () => {
  it("matches an industry case-insensitively and ignores surrounding whitespace", async () => {
    await renderTree();
    search("  SEMICOND ");
    expect(screen.getByText("Semiconductors")).toBeTruthy();
    expect(screen.queryByText("Software—Application")).toBeNull();
    expect(screen.queryByText("Energy")).toBeNull();
  });

  it("keeps every industry of a sector matched by name", async () => {
    await renderTree();
    search("energy");
    expect(screen.getByText("Oil & Gas Integrated")).toBeTruthy();
    expect(screen.queryByText("Technology")).toBeNull();
  });

  it("reports when nothing matches", async () => {
    await renderTree();
    search("zzz");
    expect(screen.getByText("No matches.")).toBeTruthy();
  });
});
