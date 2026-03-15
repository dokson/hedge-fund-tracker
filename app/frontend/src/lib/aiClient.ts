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
  { id: "github",      name: "GitHub Models",    envKey: "GITHUB_TOKEN",       link: "https://github.com/settings/tokens",      hint: "ghp_…" },
  { id: "google",      name: "Google AI Studio", envKey: "GOOGLE_API_KEY",     link: "https://aistudio.google.com/app/apikey",  hint: "AIza…" },
  { id: "groq",        name: "Groq",             envKey: "GROQ_API_KEY",       link: "https://console.groq.com/keys",           hint: "gsk_…" },
  { id: "huggingface", name: "HuggingFace",      envKey: "HF_TOKEN",           link: "https://huggingface.co/settings/tokens",  hint: "hf_…" },
  { id: "openrouter",  name: "OpenRouter",       envKey: "OPENROUTER_API_KEY", link: "https://openrouter.ai/settings/keys",     hint: "sk-or-…" },
];

// ─── Python backend AI calls ───────────────────────────────────────────────────

function _providerIdForModel(_modelId: string | undefined): null {
  return null; // provider is now resolved via ModelSelector → onProviderChange
}

export async function runPromiseScore(quarter: string, topN: number, modelId?: string): Promise<any[]> {
  const res = await fetch(`${API_BASE}/api/ai/promise-score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quarter, top_n: topN, model_id: modelId || null, provider_id: _providerIdForModel(modelId) }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  return res.json();
}

export async function runDueDiligence(ticker: string, quarter: string, modelId?: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/ai/due-diligence`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, quarter, model_id: modelId || null, provider_id: _providerIdForModel(modelId) }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  return res.json();
}

// ─── Streaming AI calls ────────────────────────────────────────────────────────

async function _readSSEStream(
  res: Response,
  onLog: (line: string) => void,
): Promise<any> {
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const event = JSON.parse(line.slice(6));
      if (event.type === "log") onLog(event.text);
      else if (event.type === "result") return event.data;
      else if (event.type === "error") throw new Error(event.message);
    }
  }
  throw new Error("Stream ended without result");
}

export async function runPromiseScoreStream(
  quarter: string,
  topN: number,
  modelId: string | undefined,
  providerId: string | undefined,
  onLog: (line: string) => void,
): Promise<any[]> {
  const res = await fetch(`${API_BASE}/api/ai/promise-score/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quarter, top_n: topN, model_id: modelId || null, provider_id: providerId || _providerIdForModel(modelId) }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  return _readSSEStream(res, onLog);
}

export async function runDueDiligenceStream(
  ticker: string,
  quarter: string,
  modelId: string | undefined,
  providerId: string | undefined,
  onLog: (line: string) => void,
): Promise<any> {
  const res = await fetch(`${API_BASE}/api/ai/due-diligence/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, quarter, model_id: modelId || null, provider_id: providerId || _providerIdForModel(modelId) }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  return _readSSEStream(res, onLog);
}

// ─── Env-based provider status ─────────────────────────────────────────────────

export async function getConfiguredProviders(): Promise<{ provider: AIProvider; hasKey: boolean }[]> {
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

// ─── Response parsing (kept for any local use) ────────────────────────────────

export function extractJSON<T = unknown>(response: string): T {
  const codeBlockMatch = response.match(/```(?:json|toon)?\s*\n?([\s\S]*?)```/);
  if (codeBlockMatch) {
    const block = codeBlockMatch[1].trim();
    try {
      return JSON.parse(block);
    } catch {
      return parseTOON(block) as T;
    }
  }
  const jsonMatch = response.match(/\{[\s\S]*\}/);
  if (jsonMatch) {
    try {
      return JSON.parse(jsonMatch[0]);
    } catch { /* fall through */ }
  }
  throw new Error("Could not extract structured data from AI response");
}

function parseTOON(text: string): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  const lines = text.split("\n").filter((l) => l.trim());
  let currentKey = "";
  let currentObj: Record<string, unknown> | null = null;

  for (const line of lines) {
    const indent = line.search(/\S/);
    const trimmed = line.trim();
    const colonIdx = trimmed.indexOf(":");
    if (colonIdx === -1) continue;
    const key = trimmed.slice(0, colonIdx).trim().replace(/^"|"$/g, "");
    let value: string | number | null = trimmed.slice(colonIdx + 1).trim();
    if (value.startsWith('"') && value.endsWith('"')) value = value.slice(1, -1);
    if (!value || value === "") {
      currentKey = key;
      currentObj = {};
      result[key] = currentObj;
      continue;
    }
    const num = Number(value);
    const parsedValue = value === "null" ? null : !isNaN(num) && value !== "" ? num : value;
    if (indent >= 2 && currentObj) {
      currentObj[key] = parsedValue;
    } else {
      currentObj = null;
      result[key] = parsedValue;
    }
  }
  return result;
}
