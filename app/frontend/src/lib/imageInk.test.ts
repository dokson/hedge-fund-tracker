import { describe, expect, it, vi } from "vitest";

import {
  hasLightTransparentInk,
  hasVisibleInk,
  imageNeedsDarkPlate,
  isBlankImage,
} from "./imageInk";

/** RGBA bytes for a run of identical pixels. */
const pixels = (count: number, rgba: [number, number, number, number]) =>
  new Uint8ClampedArray(Array.from({ length: count }, () => rgba).flat());

describe("hasVisibleInk", () => {
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

describe("hasLightTransparentInk", () => {
  it("uses a dark plate for predominantly light artwork over transparency", () => {
    const data = pixels(16, [0, 0, 0, 0]);
    data.set(pixels(8, [255, 255, 255, 255]), 0);
    data.set([255, 153, 0, 255], 4 * 8);

    expect(hasLightTransparentInk(data)).toBe(true);
  });

  it("keeps a white plate for dark and colored transparent artwork", () => {
    const data = pixels(16, [0, 0, 0, 0]);
    data.set(pixels(8, [20, 80, 200, 255]), 0);
    data.set([255, 255, 255, 255], 4 * 8);

    expect(hasLightTransparentInk(data)).toBe(false);
  });

  it("does not treat a baked-in white background as transparent light artwork", () => {
    const data = pixels(16, [255, 255, 255, 255]);
    data.set([0, 0, 0, 255], 4 * 8);

    expect(hasLightTransparentInk(data)).toBe(false);
  });

  it("does not assign a dark plate to an empty transparent source", () => {
    expect(hasLightTransparentInk(pixels(16, [255, 255, 255, 0]))).toBe(false);
  });
});

describe("unreadable source pixels", () => {
  it("keeps the white plate and does not classify an unreadable image as blank", () => {
    const img = document.createElement("img");
    Object.defineProperties(img, {
      naturalWidth: { value: 32 },
      naturalHeight: { value: 32 },
    });
    const context = vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => {
      throw new Error("Pixel access unavailable");
    });
    try {
      expect(imageNeedsDarkPlate(img)).toBe(false);
      expect(isBlankImage(img)).toBe(false);
    } finally {
      context.mockRestore();
    }
  });
});
