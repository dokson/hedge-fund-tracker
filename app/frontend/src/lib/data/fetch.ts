/**
 * Shared fetch/caching plumbing for the data layer: CSV download + parse, the
 * in-memory TTL cache every loader funnels through, and file save/download.
 */

import Papa from "papaparse";
import { DATABASE_URL, IS_GH_PAGES_MODE, BASE_PATH } from "../config";

export async function fetchCSV<T>(url: string, requiredColumns?: readonly string[]): Promise<T[]> {
  const fullUrl = IS_GH_PAGES_MODE
    ? `${BASE_PATH}${url}`
    : `${DATABASE_URL}${url.replace(/^\/database/, "")}`;
  const response = await fetch(fullUrl);
  if (!response.ok) throw new Error(`Failed to fetch ${url}: ${response.status}`);
  const text = await response.text();

  return new Promise((resolve, reject) => {
    Papa.parse<T>(text, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        // A renamed/removed column would otherwise surface as silent
        // `undefined` fields deep in the loaders — fail loudly at the source.
        if (requiredColumns) {
          const fields = results.meta.fields ?? [];
          const missing = requiredColumns.filter((c) => !fields.includes(c));
          if (missing.length > 0) {
            reject(new Error(`${url} is missing expected column(s): ${missing.join(", ")}`));
            return;
          }
        }
        resolve(results.data);
      },
      error: (err: Error) => reject(err),
    });
  });
}

// ---------- Simple in-memory cache ----------

const cache = new Map<string, { data: unknown; ts: number }>();
const CACHE_TTL = 10 * 60 * 1000; // 10 minutes

export async function cachedFetch<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const cached = cache.get(key);
  if (cached && Date.now() - cached.ts < CACHE_TTL) return cached.data as T;
  const data = await fetcher();
  cache.set(key, { data, ts: Date.now() });
  return data;
}

export function clearCache(key?: string) {
  if (key) {
    cache.delete(key);
  } else {
    cache.clear();
  }
}

// ---------- File save / download ----------

export async function saveFileToDisk(content: string, filePath: string): Promise<void> {
  if (IS_GH_PAGES_MODE) {
    // In GitHub Pages mode, download the file instead of saving to server
    downloadFile(content, filePath.split("/").pop() || filePath);
    return;
  }
  const res = await fetch(`${window.location.origin}/database/${filePath}`, {
    method: "PUT",
    headers: { "Content-Type": "text/plain" },
    body: content,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Unknown error" }));
    throw new Error(err.error || "Failed to save file");
  }
}

/** @deprecated Use saveFileToDisk instead */
export function downloadFile(content: string, filename: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
