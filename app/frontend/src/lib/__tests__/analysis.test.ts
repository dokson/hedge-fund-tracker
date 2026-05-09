import { describe, it, expect } from "vitest";
import { generateHedgeFundsCSV, generateExcludedFundsCSV, generateModelsCSV } from "../dataService";
import type { HedgeFund, ExcludedHedgeFund, AIModel } from "../dataService";

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
  });

  it("should generate CSV with multiple fund rows", () => {
    const funds: HedgeFund[] = [
      {
        cik: "0001111111",
        fund: "Fund A",
        manager: "Manager A",
        denomination: "Fund A LP",
        ciks: "",
        url: "",
      },
      {
        cik: "0002222222",
        fund: "Fund B",
        manager: "Manager B",
        denomination: "Fund B LLC",
        ciks: "0003333333",
        url: "https://fund-b.example.com/",
      },
    ];

    const csv = generateHedgeFundsCSV(funds);
    const lines = csv.split("\n").filter((l) => l);

    expect(lines).toHaveLength(3);
    expect(lines[0]).toContain("CIK");
    expect(lines[0]).toContain("URL");
    expect(lines[1]).toContain("Fund A");
    expect(lines[2]).toContain("0003333333");
    expect(lines[2]).toContain("https://fund-b.example.com/");
  });

  it("should handle empty funds array with trailing newline", () => {
    const csv = generateHedgeFundsCSV([]);

    expect(csv).toBe('"CIK","Fund","Manager","Denomination","CIKs","URL"\n\n');
  });
});

describe("generateExcludedFundsCSV", () => {
  it("should generate CSV with correct columns", () => {
    const funds: ExcludedHedgeFund[] = [
      {
        cik: "0001067983",
        fund: "Berkshire Hathaway",
        manager: "Warren Buffett",
        denomination: "Berkshire Hathaway Inc",
        ciks: "",
        url: "https://www.berkshirehathaway.com/",
      },
    ];

    const csv = generateExcludedFundsCSV(funds);

    expect(csv).toContain('"CIK","Fund","Manager","Denomination","CIKs","URL"');
    expect(csv).toContain("Warren Buffett");
    expect(csv).toContain("berkshirehathaway");
  });
});

describe("generateModelsCSV", () => {
  it("should generate CSV with header and model rows", () => {
    const models: AIModel[] = [
      { id: "gpt-4o", description: "GPT-4o", client: "GitHub" },
      { id: "gemini-2.0-flash", description: "Gemini 2.0 Flash", client: "Google" },
    ];

    const csv = generateModelsCSV(models);
    const lines = csv.split("\n").filter((l) => l);

    expect(lines).toHaveLength(3);
    expect(lines[0]).toBe('"ID","Description","Client"');
    expect(lines[1]).toContain("gpt-4o");
    expect(lines[2]).toContain("Google");
  });
});
