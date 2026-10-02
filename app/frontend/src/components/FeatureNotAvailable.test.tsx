import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import FeatureNotAvailable from "./FeatureNotAvailable";

describe("FeatureNotAvailable", () => {
  it("names the feature and links to the project repository", () => {
    const { getByText, getByRole } = render(<FeatureNotAvailable feature="AI Ranking" />);
    expect(getByText("AI Ranking")).toBeDefined();
    expect(getByText(/requires a local AI backend/i)).toBeDefined();
    const link = getByRole("link", { name: /view on github/i });
    expect(link.getAttribute("href")).toBe("https://github.com/dokson/hedge-fund-tracker");
  });
});
