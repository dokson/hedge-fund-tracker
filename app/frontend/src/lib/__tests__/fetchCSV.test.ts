import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchCSV } from "../data/fetch";

function mockCsvFetch(body: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(body, { status: 200 })),
  );
}

describe("fetchCSV required-column validation", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("resolves when every required column is present", async () => {
    mockCsvFetch("Alpha,Beta\n1,2\n");
    const rows = await fetchCSV<{ Alpha: string; Beta: string }>("/database/x.csv", [
      "Alpha",
      "Beta",
    ]);
    expect(rows).toEqual([{ Alpha: "1", Beta: "2" }]);
  });

  it("rejects with a descriptive error when a column is missing", async () => {
    mockCsvFetch("Alpha\n1\n");
    await expect(fetchCSV("/database/x.csv", ["Alpha", "Beta"])).rejects.toThrow(/Beta/);
  });

  it("keeps working without a required-column list", async () => {
    mockCsvFetch("Alpha\n1\n");
    await expect(fetchCSV("/database/x.csv")).resolves.toEqual([{ Alpha: "1" }]);
  });
});
