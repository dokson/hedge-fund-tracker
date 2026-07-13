import { describe, expect, it } from "vitest";

import { toDueDiligenceReport } from "../dueDiligence";

const VALID = {
  ticker: "TST",
  company: "Test Corp",
  current_price: "$10.00",
  filing_date_price: "$9.50",
  price_delta_percentage: "+5.26%",
  analysis: { business_summary: "A test company." },
  investment_thesis: { overall_sentiment: "Bullish" },
};

describe("toDueDiligenceReport", () => {
  it("accepts a well-formed report", () => {
    expect(toDueDiligenceReport(VALID)).toEqual(VALID);
  });

  it("accepts a report without the optional sections", () => {
    const { analysis: _a, investment_thesis: _t, ...minimal } = VALID;
    expect(toDueDiligenceReport(minimal)).toEqual(minimal);
  });

  it("rejects non-objects and null", () => {
    expect(toDueDiligenceReport(null)).toBeNull();
    expect(toDueDiligenceReport("oops")).toBeNull();
    expect(toDueDiligenceReport(42)).toBeNull();
  });

  it("rejects a report missing a required string field", () => {
    const { ticker: _ticker, ...rest } = VALID;
    expect(toDueDiligenceReport(rest)).toBeNull();
    expect(toDueDiligenceReport({ ...VALID, company: 7 })).toBeNull();
  });

  it("rejects a report whose optional section is not an object", () => {
    expect(toDueDiligenceReport({ ...VALID, analysis: "not an object" })).toBeNull();
  });
});
