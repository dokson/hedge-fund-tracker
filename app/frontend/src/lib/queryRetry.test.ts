import { describe, expect, it } from "vitest";

import { DataFormatError, HttpError } from "./data/fetch";
import { shouldRetryQuery } from "./queryRetry";

describe("shouldRetryQuery", () => {
  it("retries transient failures up to three times", () => {
    const err = new Error("network");
    expect(shouldRetryQuery(0, err)).toBe(true);
    expect(shouldRetryQuery(2, err)).toBe(true);
    expect(shouldRetryQuery(3, err)).toBe(false);
  });

  it("retries server errors", () => {
    expect(shouldRetryQuery(0, new HttpError("boom", 503))).toBe(true);
  });

  it("never retries client errors", () => {
    expect(shouldRetryQuery(0, new HttpError("missing", 404))).toBe(false);
  });

  it("never retries a malformed payload", () => {
    expect(shouldRetryQuery(0, new DataFormatError("bad shape"))).toBe(false);
  });
});
