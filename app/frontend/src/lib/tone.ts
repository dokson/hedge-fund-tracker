/** Semantic tones shared by text, chips and deltas. */
export type Tone = "positive" | "negative" | "warning" | "neutral";

/** Tone of a signed value: above zero positive, below negative, zero neutral. */
export const signTone = (value: number): Tone =>
  value > 0 ? "positive" : value < 0 ? "negative" : "neutral";

/** Text colour class for a signed value; zero reads muted. */
export const toneClass = (value: number): string =>
  value > 0 ? "delta-positive" : value < 0 ? "delta-negative" : "text-muted-foreground";

/** Tone of a position change: openings and additions positive, cuts and exits negative. */
export const changeTone = (deltaType: string): Tone =>
  deltaType === "NEW" || deltaType === "INCREASE"
    ? "positive"
    : deltaType === "DECREASE" || deltaType === "CLOSED" || deltaType === "CLOSE"
      ? "negative"
      : "neutral";

const CHANGE_LABEL: Record<string, string> = {
  NEW: "New",
  INCREASE: "Increased",
  DECREASE: "Decreased",
  CLOSED: "Closed",
  CLOSE: "Closed",
  "NO CHANGE": "No change",
  UNKNOWN: "Unknown",
};

/**
 * How a position-change token reads on screen: sentence case, never the data's capitals (a
 * small all-caps label shouts, Hallmark). The tokens themselves stay as they are in the data
 * layer, which compares them (`delta === "NEW"`); only what is drawn goes through here.
 */
export const changeLabel = (token: string): string => CHANGE_LABEL[token] ?? token;
