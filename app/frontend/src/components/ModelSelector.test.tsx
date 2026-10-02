/**
 * Regression tests for ModelSelector — guards the "Unsupported provider None"
 * bug where the displayed default model wasn't propagated to the parent's
 * providerId state, causing AI requests to be sent with provider_id: null.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ModelSelector from "./ModelSelector";
import type { getModels as getModelsType } from "@/lib/dataService";
import type { getConfiguredProviders as getConfiguredProvidersType } from "@/lib/aiClient";

vi.mock("@/lib/dataService", () => ({
  getModels: vi.fn<typeof getModelsType>(async () => [
    { id: "gemini-3.1-flash-lite", description: "Gemini 3.1 Flash Lite", client: "Google" },
    { id: "openai/gpt-oss-120b", description: "GPT-OSS 120B", client: "Groq" },
  ]),
}));

vi.mock("@/lib/aiClient", async () => {
  const actual = await vi.importActual<typeof import("@/lib/aiClient")>("@/lib/aiClient");
  return {
    ...actual,
    getConfiguredProviders: vi.fn<typeof getConfiguredProvidersType>(async () => [
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

  it("propagates the default model and a non-empty provider id on initial render", async () => {
    const onChange = vi.fn<(modelId: string) => void>();
    const onProviderChange = vi.fn<(providerId: string) => void>();

    renderWithClient(
      <ModelSelector value="" onChange={onChange} onProviderChange={onProviderChange} />,
    );

    // The bug: parent's empty value falls back to availableModels[0] in the
    // displayed select, but parent state stays empty, so the request fires
    // with provider_id: null and the backend rejects "Unsupported provider None".
    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith("gemini-3.1-flash-lite");
      expect(onProviderChange).toHaveBeenCalledWith("google");
    });
    expect(onProviderChange).not.toHaveBeenCalledWith("");
  });
});
