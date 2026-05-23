/**
 * Regression tests for ModelSelector — guards the "Unsupported provider None"
 * bug where the displayed default model wasn't propagated to the parent's
 * providerId state, causing AI requests to be sent with provider_id: null.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ModelSelector from "./ModelSelector";

vi.mock("@/lib/dataService", () => ({
  getModels: vi.fn(async () => [
    { id: "gemini-3.1-flash-lite", description: "Gemini 3.1 Flash Lite", client: "Google" },
    { id: "llama-3.3-70b-versatile", description: "Llama 3.3 70B", client: "Groq" },
  ]),
}));

vi.mock("@/lib/aiClient", async () => {
  const actual = await vi.importActual<typeof import("@/lib/aiClient")>("@/lib/aiClient");
  return {
    ...actual,
    getConfiguredProviders: vi.fn(async () => [
      { provider: actual.AI_PROVIDERS.find((p) => p.id === "google")!, hasKey: true },
      { provider: actual.AI_PROVIDERS.find((p) => p.id === "groq")!, hasKey: true },
    ]),
  };
});

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("ModelSelector — provider propagation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("propagates default model id + provider id to parent on initial render (no manual selection)", async () => {
    const onChange = vi.fn();
    const onProviderChange = vi.fn();

    renderWithClient(
      <ModelSelector value="" onChange={onChange} onProviderChange={onProviderChange} />,
    );

    // The bug: parent's empty value falls back to availableModels[0] in the
    // displayed select, but parent state (selectedModel/selectedProviderId)
    // stays empty → request fires with provider_id: null → backend rejects
    // with "Unsupported provider None". The fix syncs the fallback up.
    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith("gemini-3.1-flash-lite");
      expect(onProviderChange).toHaveBeenCalledWith("google");
    });
  });

  it("never propagates an empty provider id when a model is displayed", async () => {
    const onChange = vi.fn();
    const onProviderChange = vi.fn();

    renderWithClient(
      <ModelSelector value="" onChange={onChange} onProviderChange={onProviderChange} />,
    );

    await waitFor(() => {
      expect(onProviderChange).toHaveBeenCalled();
    });
    // Critical: no call should have passed "" — that's what produced
    // provider_id: null on the wire.
    for (const call of onProviderChange.mock.calls) {
      expect(call[0]).not.toBe("");
    }
  });
});
