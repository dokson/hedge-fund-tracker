/**
 * AI model catalogue (database/models.csv) and provider display metadata.
 */

import { cachedFetch, fetchCSV } from "./fetch";
import type { AIModel, RawModel } from "./types";

export const MODEL_PROVIDERS = ["GitHub", "Groq", "Google", "HuggingFace", "OpenRouter"] as const;

export type ModelProvider = (typeof MODEL_PROVIDERS)[number];

/** Display names for CSV client values (used in UI only) */
export const PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  GitHub: "GitHub Models",
  Google: "Google AI Studio",
  Groq: "Groq",
  HuggingFace: "HuggingFace",
  OpenRouter: "OpenRouter",
};

export async function getModels(): Promise<AIModel[]> {
  return cachedFetch("models", async () => {
    const raw = await fetchCSV<RawModel>("/database/models.csv", [
      "ID",
      "Description",
      "Client",
    ] satisfies readonly (keyof RawModel)[]);
    return raw.map((r) => ({
      id: r.ID,
      description: r.Description,
      client: r.Client,
    }));
  });
}

export function generateModelsCSV(models: AIModel[]): string {
  return (
    '"ID","Description","Client"\n' +
    models.map((m) => `"${m.id}","${m.description}","${m.client}"`).join("\n") +
    "\n"
  );
}
