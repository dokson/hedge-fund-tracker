/** Semantic tones shared by text, chips and deltas. */
export type Tone = "positive" | "negative" | "warning" | "neutral";

/** Tone of a signed value: above zero positive, below negative, zero neutral. */
export const signTone = (value: number): Tone =>
  value > 0 ? "positive" : value < 0 ? "negative" : "neutral";

/** Text colour class for a signed value; zero reads muted. */
export const toneClass = (value: number): string =>
  value > 0 ? "delta-positive" : value < 0 ? "delta-negative" : "text-muted-foreground";
