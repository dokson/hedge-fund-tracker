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
