/**
 * Branded type representing a valid quarter identifier in the form "YYYYQ[1-4]".
 * Use isQuarter() or assertQuarter() to narrow strings from untyped sources (API, CSV).
 */
export type Quarter = `${number}Q${1 | 2 | 3 | 4}`;

const QUARTER_RE = /^\d{4}Q[1-4]$/;

export function isQuarter(value: string): value is Quarter {
  return QUARTER_RE.test(value);
}

export function assertQuarter(value: string): Quarter {
  if (!isQuarter(value)) {
    throw new Error(`Invalid quarter: ${value}`);
  }
  return value;
}

/**
 * Filter and sort a list of untyped strings into valid Quarters.
 */
export function parseQuarters(values: readonly string[]): readonly Quarter[] {
  return values.filter(isQuarter).sort() as readonly Quarter[];
}

/** Share of the last usable quarter's filings a newer quarter needs to count as usable. */
export const MIN_QUARTER_COVERAGE = 0.5;

/**
 * The newest quarter with enough filings to be analysed (Python `last_usable_quarter`).
 * An incomplete quarter never becomes the baseline for the next one; the oldest is always usable.
 */
export function latestUsableQuarter(
  filingsPerQuarter: Readonly<Record<string, number>>,
): Quarter | null {
  let usable: Quarter | null = null;
  let baseline = 0;
  for (const quarter of parseQuarters(Object.keys(filingsPerQuarter))) {
    const count = filingsPerQuarter[quarter];
    if (usable === null || count >= MIN_QUARTER_COVERAGE * baseline) {
      usable = quarter;
      baseline = count;
    }
  }
  return usable;
}

/** How far behind the board's quarter a fund's last filing is. */
export type FilingFreshness = "current" | "late" | "stale";

/** A fund this many quarters behind, or fewer, is late; beyond it, stale. */
const MAX_LATE_QUARTERS = 2;

/** Position of a "YYYYQN" quarter on a continuous quarter count. */
const quarterIndex = (quarter: string) => Number(quarter.slice(0, 4)) * 4 + Number(quarter[5]) - 1;

/** Whole quarters a fund's last filing trails the board's quarter; 0 when level or ahead. */
export function quartersBehind(
  fundQuarter: string | null,
  boardQuarter: string | null,
): number | null {
  if (fundQuarter === null || boardQuarter === null) return null;
  return Math.max(0, quarterIndex(boardQuarter) - quarterIndex(fundQuarter));
}

/**
 * Current on the board's quarter or past it, late up to two quarters behind, stale beyond that.
 */
export function filingFreshness(
  fundQuarter: string | null,
  boardQuarter: string | null,
): FilingFreshness | null {
  const behind = quartersBehind(fundQuarter, boardQuarter);
  if (behind === null) return null;
  if (behind === 0) return "current";
  return behind <= MAX_LATE_QUARTERS ? "late" : "stale";
}

/** The quarter at a position of the continuous quarter count (inverse of `quarterIndex`). */
const quarterAt = (index: number) => `${Math.floor(index / 4)}Q${(index % 4) + 1}` as Quarter;

/**
 * What a fund's changes in `quarter` are measured against: its last filing before that quarter
 * and the quarters in between with no 13F on file (a fund that skips a filing is compared with
 * the one before, so its changes span them). Null for the fund's first quarter on file.
 */
export function comparisonBasis(
  fundQuarters: readonly string[],
  quarter: string,
): { previous: Quarter; skipped: Quarter[] } | null {
  const earlier = parseQuarters(fundQuarters).filter((q) => q < quarter);
  const previous = earlier.at(-1);
  if (previous === undefined) return null;
  const skipped: Quarter[] = [];
  for (let i = quarterIndex(previous) + 1; i < quarterIndex(quarter); i++) {
    skipped.push(quarterAt(i));
  }
  return { previous, skipped };
}
