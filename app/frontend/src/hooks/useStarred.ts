import { useState, useCallback, useEffect } from "react";

const STORAGE_KEY_PREFIX = "starred_";

function readStarred(type: "stock" | "fund"): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_PREFIX + type);
    if (raw) return new Set(JSON.parse(raw));
  } catch {}
  return new Set();
}

function writeStarred(type: "stock" | "fund", set: Set<string>) {
  localStorage.setItem(STORAGE_KEY_PREFIX + type, JSON.stringify([...set]));
}

export function useStarred(type: "stock" | "fund") {
  const [starred, setStarred] = useState<Set<string>>(() => readStarred(type));

  // Sync across tabs
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY_PREFIX + type) {
        setStarred(readStarred(type));
      }
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, [type]);

  const toggle = useCallback((id: string) => {
    setStarred((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      writeStarred(type, next);
      return next;
    });
  }, [type]);

  const isStarred = useCallback((id: string) => starred.has(id), [starred]);

  return { starred, toggle, isStarred };
}
