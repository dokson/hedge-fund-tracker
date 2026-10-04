import { describe, expect, it } from "vitest";

import { rankFunds, sortRanking } from "../fundRanking";
import type { RawFundPerformanceRow } from "../data/types";

function row(
  fund: string,
  quarter: string,
  fundReturn: number,
  benchmarkReturn: number,
  unpriced = 0,
): RawFundPerformanceRow {
  return {
    fund,
    quarter,
    fund_return: String(fundReturn),
    benchmark_return: String(benchmarkReturn),
    fund_cum_return: "",
    benchmark_cum_return: "",
    unpriced_weight: String(unpriced),
  };
}

const QUARTERS = ["2025Q2", "2025Q3", "2025Q4"];
const INDEX = [0.1, 0.0, 0.1];

/** A fund measured on every quarter, with the index's returns alongside. */
function fund(name: string, returns: number[], unpriced: number[] = []): RawFundPerformanceRow[] {
  return QUARTERS.map((q, i) => row(name, q, returns[i] ?? 0, INDEX[i] ?? 0, unpriced[i] ?? 0));
}

describe("rankFunds", () => {
  it("compounds each fund and the index over the common window", () => {
    const ranking = rankFunds(fund("A", [0.2, -0.1, 0.1]));
    expect(ranking.quarters).toEqual(QUARTERS);
    expect(ranking.startQuarter).toBe("2025Q1");
    expect(ranking.benchmarkReturn).toBeCloseTo(1.1 * 1.0 * 1.1 - 1);
    const [a] = ranking.funds;
    expect(a?.cumReturn).toBeCloseTo(1.2 * 0.9 * 1.1 - 1);
    expect(a?.excess).toBeCloseTo(1.2 * 0.9 * 1.1 - 1.21);
  });

  it("counts the quarters beating the index and the worst quarter", () => {
    const [a] = rankFunds(fund("A", [0.2, -0.1, 0.1])).funds;
    expect(a?.beats).toBe(1);
    expect(a?.total).toBe(3);
    expect(a?.worstQuarter).toBeCloseTo(-0.1);
  });

  it("measures consistency as mean excess over its sample deviation", () => {
    const [a] = rankFunds(fund("A", [0.2, 0.1, 0.3])).funds;
    // excess per quarter: 0.1, 0.1, 0.2 -> mean 0.1333, sample sd 0.0577
    expect(a?.consistency).toBeCloseTo(0.13333 / 0.057735, 3);
  });

  it("has no consistency when the excess never varies", () => {
    const [a] = rankFunds(fund("A", [0.2, 0.1, 0.2])).funds;
    expect(a?.consistency).toBeNull();
  });

  it("ranks a fund missing quarters on its own, against the index on the same quarters", () => {
    const partial = fund("B", [0.5, 0.5, 0.5]).slice(1);
    const ranking = rankFunds([...fund("A", [0.1, 0.1, 0.1]), ...partial]);
    const b = ranking.funds.find((f) => f.fund === "B");
    expect(ranking.funds.map((f) => f.fund).sort()).toEqual(["A", "B"]);
    expect(b?.total).toBe(2);
    expect(b?.partial).toBe(true);
    expect(b?.cumReturn).toBeCloseTo(1.5 * 1.5 - 1);
    expect(b?.excess).toBeCloseTo(1.5 * 1.5 - 1.1);
    expect(ranking.funds.find((f) => f.fund === "A")?.partial).toBe(false);
  });

  it("flags a fund whose worst quarter left too much of the book unpriced", () => {
    const [a] = rankFunds(fund("A", [0.1, 0.1, 0.1], [0, 0.25, 0.01])).funds;
    expect(a?.maxUnpriced).toBeCloseTo(0.25);
    expect(a?.lowCoverage).toBe(true);
  });

  it("is empty without data", () => {
    expect(rankFunds([])).toEqual({
      quarters: [],
      startQuarter: "",
      benchmarkReturn: 0,
      funds: [],
    });
  });
});

describe("sortRanking", () => {
  const ranking = rankFunds([...fund("Low", [0.0, 0.0, 0.0]), ...fund("High", [0.3, 0.2, 0.1])]);

  it("sorts by the chosen key and direction without mutating the input", () => {
    const before = ranking.funds.map((f) => f.fund);
    expect(sortRanking(ranking.funds, "cumReturn", "desc").map((f) => f.fund)).toEqual([
      "High",
      "Low",
    ]);
    expect(sortRanking(ranking.funds, "cumReturn", "asc").map((f) => f.fund)).toEqual([
      "Low",
      "High",
    ]);
    expect(ranking.funds.map((f) => f.fund)).toEqual(before);
  });

  it("puts funds without a consistency figure last in either direction", () => {
    const flat = rankFunds([...fund("Flat", [0.2, 0.1, 0.2]), ...fund("Ok", [0.2, 0.1, 0.3])]);
    expect(sortRanking(flat.funds, "consistency", "desc").at(-1)?.fund).toBe("Flat");
    expect(sortRanking(flat.funds, "consistency", "asc").at(-1)?.fund).toBe("Flat");
  });
});
