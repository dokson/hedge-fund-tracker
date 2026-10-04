/** Formatting shared by the performance views. */

/** A return fraction as a signed percentage: `0.078` → `+7.8%`. */
export const pctFrac = (value: number) => `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;

/** Percentage points, signed: `1.75` → `+1.8 pp`. */
export const pp = (value: number) => `${value > 0 ? "+" : ""}${value.toFixed(1)} pp`;

/** Positive / negative / neutral text tone for a signed value. */
export const toneClass = (value: number) =>
  value > 0 ? "delta-positive" : value < 0 ? "delta-negative" : "text-muted-foreground";
