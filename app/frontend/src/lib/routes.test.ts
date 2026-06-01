/**
 * Tests for the centralised route module. These paths are the single source of
 * truth for in-app navigation, so the builders' encoding contract is
 * load-bearing (a fund name with spaces/ampersands must round-trip safely).
 */
import { describe, expect, it } from "vitest";

import { ROUTES, stockPath, fundPath, stocksByIndustry, aiDiligenceFor } from "./routes";

describe("ROUTES", () => {
  it("exposes the canonical static paths", () => {
    expect(ROUTES.home).toBe("/");
    expect(ROUTES.latest).toBe("/latest");
    expect(ROUTES.stocks).toBe("/stocks");
    expect(ROUTES.funds).toBe("/funds");
    expect(ROUTES.stock).toBe("/stock");
  });
});

describe("path builders", () => {
  it("builds a stock path, encoding unsafe characters", () => {
    expect(stockPath("ABCD")).toBe("/stock/ABCD");
    expect(stockPath("A B")).toBe("/stock/A%20B");
  });

  it("builds a fund path with spaces encoded", () => {
    expect(fundPath("Foo Bar Capital")).toBe("/funds/Foo%20Bar%20Capital");
  });

  it("builds the industry-filtered stocks query", () => {
    expect(stocksByIndustry("Tech & Media")).toBe("/stocks?industry=Tech%20%26%20Media");
  });

  it("builds the AI due diligence query for a ticker", () => {
    expect(aiDiligenceFor("XYZ")).toBe("/ai-diligence?ticker=XYZ");
  });
});
