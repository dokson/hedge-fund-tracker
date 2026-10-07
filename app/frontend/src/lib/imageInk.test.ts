import { describe, expect, it } from "vitest";

import { hasVisibleInk } from "./imageInk";

/** RGBA bytes for a run of identical pixels. */
const pixels = (count: number, rgba: [number, number, number, number]) =>
  new Uint8ClampedArray(Array.from({ length: count }, () => rgba).flat());

describe("hasVisibleInk", () => {
  it("is false for a fully transparent image (a favicon that draws nothing)", () => {
    expect(hasVisibleInk(pixels(256, [0, 0, 0, 0]))).toBe(false);
  });

  it("is false for an all-white image, which vanishes on the white logo tile", () => {
    expect(hasVisibleInk(pixels(256, [255, 255, 255, 255]))).toBe(false);
  });

  it("is true as soon as one opaque, non-white pixel is drawn", () => {
    const data = pixels(256, [0, 0, 0, 0]);
    data.set([20, 80, 200, 255], 4 * 100);
    expect(hasVisibleInk(data)).toBe(true);
  });

  it("ignores near-invisible pixels (alpha below the visibility floor)", () => {
    expect(hasVisibleInk(pixels(256, [0, 0, 0, 10]))).toBe(false);
  });
});
