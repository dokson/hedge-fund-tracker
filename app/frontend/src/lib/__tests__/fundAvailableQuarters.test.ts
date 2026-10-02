import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearCache } from "../data/fetch";
import { getFundAvailableQuarters } from "../data/quarterData";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

/** Routes the quarter-list and per-quarter manifest endpoints; `manifest` decides each quarter's response. */
function stubApi(manifest: (quarter: string) => Response) {
  const fetchMock = vi.fn<(url: string) => Promise<Response>>(async (url) => {
    if (url.endsWith("/api/database/quarters")) return json(["2026Q1", "2026Q2"]);
    const quarter = url.split("/").at(-1) ?? "";
    return manifest(quarter);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("getFundAvailableQuarters", () => {
  beforeEach(() => clearCache());
  afterEach(() => {
    vi.unstubAllGlobals();
    clearCache();
  });

  it("lists the quarters whose manifest includes the fund", async () => {
    stubApi((q) => json(q === "2026Q2" ? ["Fund_A"] : ["Other"]));
    await expect(getFundAvailableQuarters("Fund A")).resolves.toEqual(["2026Q2"]);
  });

  it("treats a 404 manifest as the quarter being absent", async () => {
    stubApi((q) => (q === "2026Q1" ? json({}, 404) : json(["Fund_A"])));
    await expect(getFundAvailableQuarters("Fund A")).resolves.toEqual(["2026Q2"]);
  });

  it("propagates a failed manifest fetch instead of dropping the quarter", async () => {
    stubApi((q) => (q === "2026Q2" ? json({}, 503) : json(["Fund_A"])));
    await expect(getFundAvailableQuarters("Fund A")).rejects.toThrow(
      "Failed to list funds for 2026Q2",
    );
  });

  it("does not cache the failure, so a retry recovers", async () => {
    let fail = true;
    stubApi((q) => (q === "2026Q2" && fail ? json({}, 503) : json(["Fund_A"])));
    await expect(getFundAvailableQuarters("Fund A")).rejects.toThrow(
      "Failed to list funds for 2026Q2",
    );
    fail = false;
    await expect(getFundAvailableQuarters("Fund A")).resolves.toEqual(["2026Q1", "2026Q2"]);
  });
});
