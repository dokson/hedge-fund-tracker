import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function toInitCap(s: string | null | undefined): string {
  if (!s) return "";
  return s.toLowerCase().replace(/(?:^|\s|[-/])\S/g, (c) => c.toUpperCase());
}

/**
 * Case-insensitive "does any field contain the query" test, shared by every
 * in-page search box (filings, stocks, funds, config). An empty/whitespace
 * query matches everything. Centralised so the set of searchable fields and
 * the matching rule stay consistent across pages.
 */
export function matchesQuery(query: string, ...fields: (string | null | undefined)[]): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return fields.some((f) => f != null && f.toLowerCase().includes(q));
}
