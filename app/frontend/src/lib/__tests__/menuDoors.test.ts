import { describe, expect, it } from "vitest";

import { MENU_DOORS } from "../menuDoors";
import { ROUTES } from "../routes";

describe("menu doors", () => {
  it("lists the fund ranking right after the fund portfolios", () => {
    const urls = MENU_DOORS.map((d) => d.url);
    expect(urls.indexOf(ROUTES.fundRanking)).toBe(urls.indexOf(ROUTES.funds) + 1);
  });
});
