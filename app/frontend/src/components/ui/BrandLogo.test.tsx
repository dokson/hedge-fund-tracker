import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BrandLogo } from "./BrandLogo";

describe("BrandLogo", () => {
  it("serves the small webp mark with intrinsic dimensions", () => {
    const { container } = render(<BrandLogo size={28} />);
    const img = container.querySelector("img");
    expect(img?.getAttribute("src")).toMatch(/\/logo-mark\.webp$/);
    expect(img?.getAttribute("width")).toBe("28");
    expect(img?.getAttribute("height")).toBe("28");
    expect(img?.getAttribute("alt")).toBe("");
  });

  it("marks the hero copy as the high-priority image", () => {
    const { container } = render(<BrandLogo size={112} alt="Hedge Fund Tracker" priority />);
    const img = container.querySelector("img");
    expect(img?.getAttribute("fetchpriority")).toBe("high");
    expect(img?.getAttribute("alt")).toBe("Hedge Fund Tracker");
  });
});
