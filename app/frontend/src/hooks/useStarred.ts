import { useCallback, useSyncExternalStore } from "react";

type StarKind = "stock" | "fund";

const STORAGE_KEY_PREFIX = "starred_";

function parseStarred(raw: string | null): Set<string> {
  try {
    if (raw) {
      const parsed: unknown = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return new Set(parsed.filter((x): x is string => typeof x === "string"));
      }
    }
  } catch {
    // Ignore parse errors and fall back to an empty set.
  }
  return new Set();
}

function readRaw(type: StarKind): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY_PREFIX + type);
  } catch {
    return null;
  }
}

/** The last parsed set per kind, keyed by the raw text it came from: a stable snapshot. */
const cache = new Map<StarKind, { raw: string | null; set: Set<string> }>();

function snapshot(type: StarKind): Set<string> {
  const raw = readRaw(type);
  const hit = cache.get(type);
  if (hit && hit.raw === raw) return hit.set;
  const set = parseStarred(raw);
  cache.set(type, { raw, set });
  return set;
}

/** Every mounted hook on this page; a toggle anywhere re-renders them all. */
const listeners = new Set<() => void>();

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  // Other tabs write the same key: their `storage` event refreshes this page too.
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

/**
 * The starred stocks or funds, shared by every component on the page: one store over
 * localStorage, so a star set in a table shows at once in the page's starred filters (and in
 * other tabs through the `storage` event), never only after a reload.
 */
export function useStarred(type: StarKind) {
  const starred = useSyncExternalStore(
    subscribe,
    () => snapshot(type),
    () => snapshot(type),
  );

  const toggle = useCallback(
    (id: string) => {
      const next = new Set(snapshot(type));
      if (next.has(id)) next.delete(id);
      else next.add(id);
      localStorage.setItem(STORAGE_KEY_PREFIX + type, JSON.stringify([...next]));
      for (const notify of listeners) notify();
    },
    [type],
  );

  const isStarred = useCallback((id: string) => starred.has(id), [starred]);

  return { starred, toggle, isStarred };
}
