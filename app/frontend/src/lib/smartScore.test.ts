import { describe, expect, it } from "vitest";

import { compareBySmartScore } from "./smartScore";

const row = (smartScore: number, breadth: number, momentum: number, conviction: number) => ({
  smartScore,
  scoreBreadth: breadth,
  scoreMomentum: momentum,
  scoreConviction: conviction,
});

describe("compareBySmartScore", () => {
  it("puts 100-100-100 before 99.6-99.6-100 when both show the same rounded score", () => {
    const perfect = row(10, 100, 100, 100);
    const almost = row(10, 99.6, 99.6, 100);
    expect([almost, perfect].sort(compareBySmartScore)).toEqual([perfect, almost]);
  });

  it("puts 100-99-100 before 99-100-99 at the same rounded score", () => {
    const stronger = row(10, 100, 99, 100);
    const weaker = row(10, 99, 100, 99);
    expect([weaker, stronger].sort(compareBySmartScore)).toEqual([stronger, weaker]);
  });

  it("ranks by the displayed score first, whatever the components", () => {
    const higher = row(9.9, 90, 100, 100);
    const lower = row(9.8, 100, 100, 100);
    expect([lower, higher].sort(compareBySmartScore)).toEqual([higher, lower]);
  });

  it("averages only the components a stock has", () => {
    const noMomentum = {
      smartScore: 10,
      scoreBreadth: 100,
      scoreMomentum: null,
      scoreConviction: 100,
    };
    const full = row(10, 100, 99, 100);
    expect([full, noMomentum].sort(compareBySmartScore)).toEqual([noMomentum, full]);
  });

  it("is a tie when rounded score and components all match", () => {
    expect(compareBySmartScore(row(10, 100, 100, 100), row(10, 100, 100, 100))).toBe(0);
  });
});
