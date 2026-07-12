import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import FeatureNotAvailable from "./FeatureNotAvailable";

describe("FeatureNotAvailable", () => {
  it("links to the project repository", () => {
    const { getByRole } = render(<FeatureNotAvailable feature="AI Ranking" />);
    const link = getByRole("link");
    expect(link.getAttribute("href")).toBe("https://github.com/dokson/hedge-fund-tracker");
  });

  it("renders the feature name and English-only copy", () => {
    const { getByText, getByRole } = render(<FeatureNotAvailable feature="AI Ranking" />);
    expect(getByText("AI Ranking")).toBeDefined();
    expect(getByText(/requires a local AI backend/i)).toBeDefined();
    expect(getByRole("link").textContent).toMatch(/view on github/i);
  });
});
