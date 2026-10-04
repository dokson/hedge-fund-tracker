import { describe, expect, it } from "vitest";

import {
  buildFundSummaries,
  buildStockSummaries,
  fundEntityPage,
  MIN_HOLDERS_FOR_PAGE,
  parseReportedValue,
  renderFundBody,
  renderStockBody,
  stockEntityPage,
  type QuarterRow,
} from "../entityPages";
import { canonicalUrl } from "../seo";

function row(over: Partial<QuarterRow>): QuarterRow {
  return {
    fund: "Alpha",
    ticker: "AAA",
    company: "AAA CORP",
    value: 100,
    portfolioPct: 1,
    delta: "NO CHANGE",
    ...over,
  };
}

describe("parseReportedValue", () => {
  it("reads the K/M/B suffixes the quarter files use", () => {
    expect(parseReportedValue("568.43M")).toBe(568_430_000);
    expect(parseReportedValue("1.2B")).toBe(1_200_000_000);
    expect(parseReportedValue("950K")).toBe(950_000);
    expect(parseReportedValue("1234")).toBe(1234);
  });

  it("treats blanks and garbage as zero", () => {
    expect(parseReportedValue("")).toBe(0);
    expect(parseReportedValue("n/a")).toBe(0);
  });
});

describe("buildStockSummaries", () => {
  const rows = [
    row({ fund: "Alpha", value: 300, delta: "NEW" }),
    row({ fund: "Beta", value: 200, delta: "+12.5%" }),
    row({ fund: "Gamma", value: 100, delta: "-4%" }),
    row({ fund: "Delta", value: 0, delta: "CLOSE" }),
    // A second line (e.g. a convertible) for the same fund and ticker.
    row({ fund: "Alpha", value: 50, portfolioPct: 0.5, delta: "NO CHANGE" }),
    row({ ticker: "BBB", fund: "Alpha" }),
  ];
  const summaries = buildStockSummaries(rows, { AAA: "Aaa Corporation" });
  const aaa = summaries.get("AAA");

  it("groups holders by fund, ignoring closed positions", () => {
    expect(aaa?.holders.map((h) => h.fund)).toEqual(["Alpha", "Beta", "Gamma"]);
    expect(aaa?.holders[0]).toMatchObject({ value: 350, portfolioPct: 1.5 });
  });

  it("counts openers and adders as buyers, cutters and closers as sellers", () => {
    expect(aaa?.buyers).toBe(2);
    expect(aaa?.sellers).toBe(2);
  });

  it("sums the reported value and prefers the master company name", () => {
    expect(aaa?.totalValue).toBe(650);
    expect(aaa?.company).toBe("Aaa Corporation");
    expect(summaries.get("BBB")?.company).toBe("AAA CORP");
  });
});

describe("stockEntityPage", () => {
  it("only publishes stocks with enough holders and a URL-safe ticker", () => {
    const base = buildStockSummaries(
      ["A", "B", "C"].map((fund) => row({ fund, ticker: "AAA" })),
      {},
    ).get("AAA");
    expect(base).toBeDefined();
    if (!base) return;
    expect(MIN_HOLDERS_FOR_PAGE).toBe(3);
    expect(stockEntityPage(base)).not.toBeNull();
    expect(stockEntityPage({ ...base, holders: base.holders.slice(0, 2) })).toBeNull();
    // A dotted symbol would be read as a file extension by the static host.
    expect(stockEntityPage({ ...base, ticker: "BRK.B" })).toBeNull();
  });

  it("matches the live page's title, description and canonical", () => {
    const summary = buildStockSummaries(
      ["A", "B", "C"].map((fund) => row({ fund })),
      { AAA: "Aaa Corporation" },
    ).get("AAA");
    if (!summary) throw new Error("missing summary");
    const page = stockEntityPage(summary);
    expect(page?.path).toBe("/stock/AAA");
    expect(page?.title).toBe("AAA · Aaa Corporation — Hedge Fund Tracker");
    expect(page?.description).toContain("Which hedge funds hold Aaa Corporation (AAA)");
  });
});

describe("renderStockBody", () => {
  const summary = buildStockSummaries(
    [
      row({ fund: "Alpha", value: 2_000_000_000, delta: "NEW" }),
      row({ fund: "Beta", value: 500_000_000, delta: "-3%" }),
      row({ fund: "Gamma", value: 1_000_000 }),
    ],
    { AAA: "Aaa & Co" },
  ).get("AAA");
  if (!summary) throw new Error("missing summary");
  const html = renderStockBody(summary, { quarter: "2026Q2", trackedFunds: 132 });

  it("opens with a quotable fact sentence", () => {
    expect(html).toContain(
      "In 2026 Q2, 3 of the 132 tracked hedge funds reported a position in Aaa &amp; Co (AAA)",
    );
    expect(html).toContain("$2.50B");
    expect(html).toContain("1 opened or added, 1 trimmed or exited");
  });

  it("lists every holder with a link to its fund page", () => {
    expect(html).toContain(`href="${canonicalUrl("/funds/Alpha")}"`);
    expect(html).toContain("<td>NEW</td>");
    expect(html).toContain("<td>-3%</td>");
  });

  it("names the source and that it is not investment advice", () => {
    expect(html).toContain("SEC EDGAR");
    expect(html).toContain("Not investment advice");
  });
});

describe("fund pages", () => {
  const rows = [
    row({ fund: "O'Keefe", ticker: "AAA", value: 300, portfolioPct: 60, delta: "NEW" }),
    row({ fund: "O'Keefe", ticker: "BBB", value: 200, portfolioPct: 40, delta: "+5%" }),
    row({ fund: "O'Keefe", ticker: "CCC", value: 0, portfolioPct: 0, delta: "CLOSE" }),
  ];
  const fund = buildFundSummaries(rows, [
    { fund: "O'Keefe", manager: "Jane Doe", denomination: "O'Keefe Capital LP" },
  ])[0];

  it("summarises open positions, value and moves", () => {
    expect(fund).toMatchObject({ positions: 2, totalValue: 500, opened: 1, closed: 1 });
    expect(fund.holdings.map((h) => h.ticker)).toEqual(["AAA", "BBB"]);
  });

  it("matches the live page's title and canonical", () => {
    const page = fundEntityPage(fund);
    expect(page.path).toBe("/funds/O'Keefe");
    expect(page.title).toBe("O'Keefe Capital LP — Hedge Fund Tracker");
    expect(page.description).toContain("O'Keefe Capital LP's reported holdings");
  });

  it("adds the quarterly track record against the S&P 500 when it is known", () => {
    const html = renderFundBody(fund, {
      quarter: "2026Q2",
      stockPages: new Set(),
      track: [
        { quarter: "2026Q1", fundReturn: 0.1, indexReturn: 0.05, fundCum: 0.1, indexCum: 0.05 },
        { quarter: "2026Q2", fundReturn: 0.2, indexReturn: null, fundCum: 0.32, indexCum: null },
      ],
    });
    expect(html).toContain("<h2>Estimated return</h2>");
    expect(html).toContain("Since 2026 Q1 the disclosed positions returned an estimated +32.0%");
    expect(html).toContain("Not the fund's actual return");
    expect(html).toContain("<td>2026 Q1</td><td>+10.0%</td><td>+5.0%</td>");
    expect(html).toContain("<td>2026 Q2</td><td>+20.0%</td><td>—</td>");
  });

  it("leaves the track record out when there is none", () => {
    const html = renderFundBody(fund, { quarter: "2026Q2", stockPages: new Set() });
    expect(html).not.toContain("Estimated return");
  });

  it("links only holdings that have their own stock page", () => {
    const html = renderFundBody(fund, { quarter: "2026Q2", stockPages: new Set(["AAA"]) });
    expect(html).toContain("managed by Jane Doe");
    expect(html).toContain(`href="${canonicalUrl("/stock/AAA")}"`);
    expect(html).not.toContain(`href="${canonicalUrl("/stock/BBB")}"`);
    expect(html).toContain("<h1>O'Keefe Capital LP</h1>");
  });
});
