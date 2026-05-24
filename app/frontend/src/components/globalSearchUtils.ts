export type SearchHit =
  | { kind: "ticker"; ticker: string; company: string }
  | { kind: "company"; ticker: string; company: string }
  | { kind: "fund"; fund: string; manager: string; url?: string }
  | { kind: "manager"; fund: string; manager: string; url?: string };

export const MAX_PER_GROUP = 5;

/**
 * Lower score is better; -1 means "no match". Exact match beats prefix beats
 * substring; among substring matches, earlier positions rank higher. Returns
 * -1 when target is null/undefined/empty so that a missing field never crashes
 * the calling memo.
 */
export function score(query: string, target: string | null | undefined): number {
  if (!target) return -1;
  const q = query.trim().toLowerCase();
  if (!q) return -1;
  const t = target.toLowerCase();
  if (t === q) return 0;
  if (t.startsWith(q)) return 1;
  const idx = t.indexOf(q);
  return idx >= 0 ? 2 + idx : -1;
}
