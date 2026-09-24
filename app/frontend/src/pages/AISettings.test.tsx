/**
 * Model-catalogue search on the AI Settings page: it goes through the shared
 * matchesQuery helper, so it trims the query and tolerates rows with a
 * missing description.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";

import AISettingsPage from "./AISettings";
import type { AIModel } from "@/lib/dataService";

vi.mock("@/lib/dataService", async () => {
  const actual = await vi.importActual<typeof import("@/lib/dataService")>("@/lib/dataService");
  // A CSV row can reach the UI without a description; the search must not crash on it.
  const models = [
    { id: "gemini-flash", description: "Gemini Flash", client: "Google" },
    { id: "gpt-oss-20b", description: undefined, client: "Groq" },
  ] as unknown as AIModel[];
  return { ...actual, getModels: vi.fn<typeof actual.getModels>(async () => models) };
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AISettingsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function openModelsTab() {
  renderPage();
  fireEvent.click(screen.getByRole("tab", { name: /AI Models/ }));
  await screen.findByText("2 / 2 models");
}

function search(value: string) {
  fireEvent.change(screen.getByLabelText("Search model, provider"), { target: { value } });
}

describe("AI Settings model search", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 200 })),
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("ignores surrounding whitespace in the query", async () => {
    await openModelsTab();
    search("  gemini  ");
    expect(screen.getByText("1 / 2 models")).toBeTruthy();
  });

  it("still matches other fields when a row has no description", async () => {
    await openModelsTab();
    search("groq");
    expect(screen.getByText("1 / 2 models")).toBeTruthy();
  });

  it("shows every model for a whitespace-only query", async () => {
    await openModelsTab();
    search("   ");
    expect(screen.getByText("2 / 2 models")).toBeTruthy();
  });
});
