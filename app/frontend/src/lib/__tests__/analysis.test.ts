import { describe, it, expect } from "vitest";
import { generateHedgeFundsCSV, generateExcludedFundsCSV, generateModelsCSV } from "../dataService";
import type { HedgeFund, AIModel } from "../dataService";

describe("generateHedgeFundsCSV", () => {
  it("should generate CSV with header and one fund row", () => {
    const funds: HedgeFund[] = [
      {
        cik: "0001234567",
        fund: "Test Fund",
        manager: "John Doe",
        denomination: "Test Fund LP",
        ciks: "",
        url: "https://test-fund.example.com/",
      },
    ];

    const csv = generateHedgeFundsCSV(funds);

    expect(csv).toBe(
      '"CIK","Fund","Manager","Denomination","CIKs","URL"\n' +
        '"0001234567","Test Fund","John Doe","Test Fund LP","","https://test-fund.example.com/"\n',
    );
    expect(generateExcludedFundsCSV(funds)).toBe(csv);
  });
});

describe("generateModelsCSV", () => {
  it("should generate CSV with header and model rows", () => {
    const models: AIModel[] = [
      { id: "openai/gpt-oss-120b", description: "GPT-OSS 120B", client: "Groq" },
      { id: "gemini-2.0-flash", description: "Gemini 2.0 Flash", client: "Google" },
    ];

    const csv = generateModelsCSV(models);
    const lines = csv.split("\n").filter((l) => l);

    expect(lines).toHaveLength(3);
    expect(lines[0]).toBe('"ID","Description","Client"');
    expect(lines[1]).toContain("openai/gpt-oss-120b");
    expect(lines[2]).toContain("Google");
  });
});
