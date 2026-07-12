/**
 * Value parsing/formatting helpers shared across the data layer and the UI.
 */

export function parseValueString(v: string): number {
  if (!v || v === "N/A") return 0;
  const cleaned = v.replace(/[,$]/g, "");
  const match = cleaned.match(/^(-?[\d.]+)([BMK])?$/i);
  if (!match) return parseFloat(cleaned) || 0;
  const num = parseFloat(match[1]);
  const suffix = (match[2] || "").toUpperCase();
  if (suffix === "B") return num * 1_000_000_000;
  if (suffix === "M") return num * 1_000_000;
  if (suffix === "K") return num * 1_000;
  return num;
}

export function formatValue(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

export function formatPct(n: number, showSign = false): string {
  if (!isFinite(n)) return "NEW";
  const sign = showSign && n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

/**
 * Formats a number as a compact, no-dollar magnitude string (e.g. "113.69M",
 * "518.8K"), trimming trailing zeros. Mirrors the Python `format_value` style
 * used when writing the per-quarter CSVs, so aggregated rows render identically
 * to the source data.
 */
export function formatValueShort(n: number): string {
  const trim = (x: number) => parseFloat(x.toFixed(2)).toString();
  const abs = Math.abs(n);
  if (abs >= 1e12) return `${trim(n / 1e12)}T`;
  if (abs >= 1e9) return `${trim(n / 1e9)}B`;
  if (abs >= 1e6) return `${trim(n / 1e6)}M`;
  if (abs >= 1e3) return `${trim(n / 1e3)}K`;
  return trim(n);
}
