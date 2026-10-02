import { DataFormatError, HttpError } from "./data/fetch";

const MAX_RETRIES = 3;

/**
 * TanStack Query `retry` predicate: transient failures (network, 5xx) get up to
 * three attempts; client errors and malformed payloads fail at once, since
 * retrying would only delay the error the page shows.
 */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof DataFormatError) return false;
  if (error instanceof HttpError && error.status >= 400 && error.status < 500) return false;
  return failureCount < MAX_RETRIES;
}
