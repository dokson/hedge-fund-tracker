import { useState } from "react";

/**
 * Walk a list of image URLs: `src` is the current one, `next()` moves on after an error,
 * `failed` once every URL failed. A new list (another ticker or fund in the same component,
 * as when one stock page leads to another) starts over from the first URL, so one logo's
 * failure never carries over to the next.
 */
export function useFallbackSrc(candidates: readonly string[]): {
  src: string | undefined;
  failed: boolean;
  next: () => void;
} {
  const key = candidates.join("\n");
  const [attempt, setAttempt] = useState({ key, index: 0 });
  // Derived reset during render (React's documented pattern), not an effect: no frame shows
  // the old failure for the new logo.
  if (attempt.key !== key) setAttempt({ key, index: 0 });
  const index = attempt.key === key ? attempt.index : 0;
  return {
    src: candidates[index],
    failed: index >= candidates.length,
    next: () => setAttempt((a) => ({ key: a.key, index: a.index + 1 })),
  };
}
