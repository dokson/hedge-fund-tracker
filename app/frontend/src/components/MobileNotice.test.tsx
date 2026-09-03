import { fireEvent, render } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import MobileNotice, { MOBILE_NOTICE_KEY } from "./MobileNotice";

describe("MobileNotice", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("announces itself as a status, not an alert", () => {
    const { getByRole } = render(<MobileNotice />);
    expect(getByRole("status").textContent).toMatch(/wider screen/i);
  });

  it("is hidden from md up rather than unmounted, so no query is needed", () => {
    const { getByRole } = render(<MobileNotice />);
    expect(getByRole("status").className).toContain("md:hidden");
  });

  it("dismisses on Got it and records the choice for the session", () => {
    const { getByRole, queryByRole } = render(<MobileNotice />);
    fireEvent.click(getByRole("button", { name: "Got it" }));
    expect(queryByRole("status")).toBeNull();
    expect(sessionStorage.getItem(MOBILE_NOTICE_KEY)).toBe("1");
  });

  it("stays away once dismissed, without a first render that flashes", () => {
    sessionStorage.setItem(MOBILE_NOTICE_KEY, "1");
    const { queryByRole } = render(<MobileNotice />);
    expect(queryByRole("status")).toBeNull();
  });

  it("still renders when sessionStorage throws", () => {
    const original = Object.getOwnPropertyDescriptor(window, "sessionStorage");
    Object.defineProperty(window, "sessionStorage", {
      configurable: true,
      get() {
        throw new Error("blocked");
      },
    });
    try {
      const { getByRole } = render(<MobileNotice />);
      expect(() => fireEvent.click(getByRole("button", { name: "Got it" }))).not.toThrow();
    } finally {
      if (original) Object.defineProperty(window, "sessionStorage", original);
    }
  });
});
