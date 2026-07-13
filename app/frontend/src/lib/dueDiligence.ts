/**
 * Due-diligence report shape returned by the backend AI endpoint, plus the
 * runtime validation that guards the trust boundary: the stream returns
 * `unknown`, and a malformed AI response must hit the error path instead of
 * rendering `undefined` fields.
 */

export interface DueDiligenceReport {
  ticker: string;
  company: string;
  current_price: string;
  filing_date_price: string;
  price_delta_percentage: string;
  analysis?: {
    business_summary?: string;
    financial_health?: string;
    financial_health_sentiment?: string;
    valuation?: string;
    valuation_sentiment?: string;
    growth_vs_risks?: string;
    growth_vs_risks_sentiment?: string;
    institutional_sentiment?: string;
    institutional_sentiment_sentiment?: string;
  };
  investment_thesis?: {
    overall_sentiment?: string;
    thesis?: string;
    price_target?: string;
  };
}

const REQUIRED_STRING_FIELDS = [
  "ticker",
  "company",
  "current_price",
  "filing_date_price",
  "price_delta_percentage",
] as const;

const OPTIONAL_OBJECT_FIELDS = ["analysis", "investment_thesis"] as const;

/**
 * Narrows an unknown AI response to a DueDiligenceReport, or null when the
 * shape is wrong (missing/mistyped required strings, non-object sections).
 */
export function toDueDiligenceReport(value: unknown): DueDiligenceReport | null {
  if (typeof value !== "object" || value === null) return null;
  const record = value as Record<string, unknown>;
  for (const field of REQUIRED_STRING_FIELDS) {
    if (typeof record[field] !== "string") return null;
  }
  for (const field of OPTIONAL_OBJECT_FIELDS) {
    const section = record[field];
    if (section !== undefined && (typeof section !== "object" || section === null)) return null;
  }
  return value as DueDiligenceReport;
}
