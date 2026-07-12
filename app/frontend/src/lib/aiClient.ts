/**
 * AI Client — proxies all AI calls through the local Python backend.
 * API keys are managed in .env and read server-side.
 *
 * Provider/model metadata is kept here for display purposes in the UI.
 */

import { API_BASE, IS_GH_PAGES_MODE } from "./config";

export interface AIProvider {
  id: string;
  name: string;
  envKey: string;
  link: string;
  hint: string;
}

export const AI_PROVIDERS: AIProvider[] = [
  {
    id: "github",
    name: "GitHub Models",
    envKey: "GITHUB_TOKEN",
    link: "https://github.com/settings/tokens",
    hint: "ghp_…",
  },
  {
    id: "google",
    name: "Google AI Studio",
    envKey: "GOOGLE_API_KEY",
    link: "https://aistudio.google.com/app/apikey",
    hint: "AIza…",
  },
  {
    id: "groq",
    name: "Groq",
    envKey: "GROQ_API_KEY",
    link: "https://console.groq.com/keys",
    hint: "gsk_…",
  },
  {
    id: "huggingface",
    name: "HuggingFace",
    envKey: "HF_TOKEN",
    link: "https://huggingface.co/settings/tokens",
    hint: "hf_…",
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    envKey: "OPENROUTER_API_KEY",
    link: "https://openrouter.ai/settings/keys",
    hint: "sk-or-…",
  },
];

// ─── Python backend AI calls ───────────────────────────────────────────────────

function _providerIdForModel(_modelId: string | undefined): null {
  return null; // provider is now resolved via ModelSelector → onProviderChange
}

export async function runPromiseScore(
  quarter: string,
  topN: number,
  modelId?: string,
): Promise<unknown[]> {
  const res = await fetch(`${API_BASE}/api/ai/promise-score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quarter,
      top_n: topN,
      model_id: modelId || null,
      provider_id: _providerIdForModel(modelId),
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  return res.json();
}

export async function runDueDiligence(
  ticker: string,
  quarter: string,
  modelId?: string,
): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api/ai/due-diligence`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ticker,
      quarter,
      model_id: modelId || null,
      provider_id: _providerIdForModel(modelId),
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  return res.json();
}

// ─── Streaming AI calls ────────────────────────────────────────────────────────

/** Events the backend SSE endpoints emit (see app/api/sse.py). */
type SSEEvent =
  | { type: "log"; text: string }
  | { type: "result"; data: unknown }
  | { type: "error"; message: string };

/**
 * Parse one SSE `data:` payload into a validated event. Returns null for
 * malformed or unknown payloads so a bad line is skipped instead of leaking
 * undefined into log/result consumers (or throwing a raw SyntaxError).
 */
export function parseSSEEvent(json: string): SSEEvent | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(json);
  } catch {
    return null;
  }
  if (typeof parsed !== "object" || parsed === null || !("type" in parsed)) return null;
  if (parsed.type === "log") {
    return "text" in parsed && typeof parsed.text === "string"
      ? { type: "log", text: parsed.text }
      : null;
  }
  if (parsed.type === "result") {
    return { type: "result", data: "data" in parsed ? parsed.data : undefined };
  }
  if (parsed.type === "error") {
    const message =
      "message" in parsed && typeof parsed.message === "string"
        ? parsed.message
        : "AI stream reported an error";
    return { type: "error", message };
  }
  return null;
}

async function _readSSEStream(res: Response, onLog: (line: string) => void): Promise<unknown> {
  if (!res.body) throw new Error("Response body is not readable");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const event = parseSSEEvent(line.slice(6));
        if (!event) continue;
        if (event.type === "log") onLog(event.text);
        else if (event.type === "result") return event.data;
        else throw new Error(event.message);
      }
    }
  } finally {
    reader.cancel().catch(() => {});
  }
  throw new Error("Stream ended without result");
}

export async function runPromiseScoreStream(
  quarter: string,
  topN: number,
  modelId: string | undefined,
  providerId: string | undefined,
  onLog: (line: string) => void,
  signal?: AbortSignal,
): Promise<unknown[]> {
  const res = await fetch(`${API_BASE}/api/ai/promise-score/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal,
    body: JSON.stringify({
      quarter,
      top_n: topN,
      model_id: modelId || null,
      provider_id: providerId || _providerIdForModel(modelId),
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  const data = await _readSSEStream(res, onLog);
  if (!Array.isArray(data)) throw new Error("Malformed AI response: expected a list of stocks");
  return data;
}

export async function runDueDiligenceStream(
  ticker: string,
  quarter: string,
  modelId: string | undefined,
  providerId: string | undefined,
  onLog: (line: string) => void,
  signal?: AbortSignal,
): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api/ai/due-diligence/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal,
    body: JSON.stringify({
      ticker,
      quarter,
      model_id: modelId || null,
      provider_id: providerId || _providerIdForModel(modelId),
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  return _readSSEStream(res, onLog);
}

// ─── Env-based provider status ─────────────────────────────────────────────────

export async function getConfiguredProviders(): Promise<
  { provider: AIProvider; hasKey: boolean }[]
> {
  if (IS_GH_PAGES_MODE) {
    return AI_PROVIDERS.map((provider) => ({ provider, hasKey: false }));
  }
  try {
    const res = await fetch(`${API_BASE}/api/settings/env`);
    const env: Record<string, string> = res.ok ? await res.json() : {};
    return AI_PROVIDERS.map((provider) => ({
      provider,
      hasKey: Boolean(env[provider.envKey]),
    }));
  } catch {
    return AI_PROVIDERS.map((provider) => ({ provider, hasKey: false }));
  }
}
