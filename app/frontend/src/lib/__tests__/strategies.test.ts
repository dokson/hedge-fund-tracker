/**
 * Guard: the TypeScript strategy definitions must match the shared canonical
 * fixture (tests/fixtures/strategies.json), generated from the Python
 * app/backtest/strategies.py. If either side drifts, this test (or its Python
 * twin) fails — so QuarterlyTrends and the backtest can't define the strategies
 * differently. Regenerate with scripts/gen_strategy_definitions.py.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { STRATEGY_DEFS } from "../strategies";

const here = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(
  readFileSync(resolve(here, "../../../../../tests/fixtures/strategies.json"), "utf-8"),
) as Array<{
  id: string;
  label: string;
  metric: string;
  ascending: boolean;
  min_holders: boolean;
  exclude_infinite_delta: boolean;
  capped: boolean;
  top_n: number | null;
  delta_sign: string | null;
  min_holders_divisor: number;
}>;

describe("STRATEGY_DEFS", () => {
  it("matches the shared canonical fixture (Python source of truth)", () => {
    const canonical = STRATEGY_DEFS.map((d) => ({
      id: d.id,
      label: d.label,
      metric: d.metric,
      ascending: d.ascending,
      min_holders: d.minHolders,
      exclude_infinite_delta: d.excludeInfiniteDelta,
      capped: d.capped,
      top_n: d.topN,
      delta_sign: d.deltaSign ?? null,
      min_holders_divisor: d.minHoldersDivisor ?? 10,
    }));
    expect(canonical).toEqual(fixture);
  });
});
