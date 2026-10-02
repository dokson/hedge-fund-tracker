import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { cachedFetch, clearCache, downloadFile } from "../data/fetch";

describe("cachedFetch", () => {
  beforeEach(() => clearCache());
  afterEach(() => clearCache());

  it("shares one in-flight request between concurrent callers", async () => {
    const fetcher = vi.fn<() => Promise<number>>(async () => 42);
    const [a, b] = await Promise.all([cachedFetch("k", fetcher), cachedFetch("k", fetcher)]);
    expect(a).toBe(42);
    expect(b).toBe(42);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("drops a rejected request so the next call retries", async () => {
    const fetcher = vi
      .fn<() => Promise<number>>()
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce(7);
    await expect(cachedFetch("k", fetcher)).rejects.toThrow("boom");
    await expect(cachedFetch("k", fetcher)).resolves.toBe(7);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("serves a resolved value from cache", async () => {
    const fetcher = vi.fn<() => Promise<string>>(async () => "v");
    await cachedFetch("k", fetcher);
    await cachedFetch("k", fetcher);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});

describe("downloadFile", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("revokes the object URL only after the click has been dispatched", () => {
    vi.useFakeTimers();
    const create = vi.fn<() => string>(() => "blob:x");
    const revoke = vi.fn<(url: string) => void>();
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    downloadFile("a,b", "f.csv");
    expect(revoke).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(revoke).toHaveBeenCalledWith("blob:x");
  });
});
