/**
 * Regression guard for the GH Pages static deployment.
 *
 * Every CSV path the frontend reads at runtime (via fetchCSV in dataService)
 * must appear in scripts/copy-database.mjs `staticFiles`, otherwise the
 * static deploy 404s on it — exactly the bug that broke /quarterly when
 * sector_hierarchy.csv was added without updating the copy script.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

// @ts-expect-error — .mjs has no .d.ts; import works at runtime.
import { staticFiles } from "./copy-database.mjs";

describe("copy-database staticFiles", () => {
  it("includes every top-level /database/*.csv path that dataService fetches", () => {
    const dataServicePath = resolve(__dirname, "..", "src", "lib", "dataService.ts");
    const source = readFileSync(dataServicePath, "utf-8");

    // Match every literal string of the form "/database/<file>.csv" that is NOT
    // a template literal interpolation (quarter-specific CSVs use template
    // literals: `/database/${quarter}/${fund}.csv`) — those live inside
    // per-quarter folders copied separately by the script.
    const literalCsvRegex = /["']\/database\/([a-z_]+\.csv)["']/gi;
    const referenced = new Set<string>();
    for (const match of source.matchAll(literalCsvRegex)) {
      referenced.add(match[1]);
    }

    expect(referenced.size).toBeGreaterThan(0); // sanity: the regex must hit something

    const missing = [...referenced].filter((file) => !staticFiles.includes(file));
    expect(missing).toEqual([]);
  });

  it("does not list a stale file that was removed from dataService", () => {
    const dataServicePath = resolve(__dirname, "..", "src", "lib", "dataService.ts");
    const source = readFileSync(dataServicePath, "utf-8");

    for (const file of staticFiles) {
      expect(source).toContain(file);
    }
  });
});
