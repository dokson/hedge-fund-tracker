import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const toastMock = vi.hoisted(() => ({
  success: vi.fn<(msg: string) => void>(),
  error: vi.fn<(msg: string) => void>(),
}));
vi.mock("sonner", () => ({ toast: toastMock }));

import type { HedgeFund } from "@/lib/dataService";
import { useInlineFundEdit } from "./useInlineFundEdit";

const FUND_A: HedgeFund = {
  cik: "1",
  fund: "Alpha",
  manager: "Ann",
  denomination: "Alpha LP",
  ciks: "1",
  url: "https://alpha.example",
};
const FUND_B: HedgeFund = { ...FUND_A, cik: "2", fund: "Beta" };

function setup(save = vi.fn<(updated: HedgeFund[]) => Promise<void>>(async () => undefined)) {
  const onSaved = vi.fn<() => void>();
  const hook = renderHook(() =>
    useInlineFundEdit({ funds: [FUND_A, FUND_B], save, successMessage: "Fund updated", onSaved }),
  );
  return { ...hook, save, onSaved };
}

describe("useInlineFundEdit", () => {
  afterEach(() => {
    toastMock.success.mockReset();
    toastMock.error.mockReset();
  });

  it("seeds the draft from the fund being edited", () => {
    const { result } = setup();
    act(() => result.current.startEdit(FUND_B));
    expect(result.current.editingCik).toBe("2");
    expect(result.current.draft.fund).toBe("Beta");
    expect(result.current.isDraftValid).toBe(true);
  });

  it("clears the edit on cancel", () => {
    const { result } = setup();
    act(() => result.current.startEdit(FUND_A));
    act(() => result.current.cancelEdit());
    expect(result.current.editingCik).toBeNull();
    expect(result.current.draft).toEqual({});
  });

  it("is invalid when a required field is blank", () => {
    const { result } = setup();
    act(() => result.current.startEdit(FUND_A));
    act(() => result.current.setDraft((d) => ({ ...d, manager: "  " })));
    expect(result.current.isDraftValid).toBe(false);
  });

  it("saves the list with only the edited fund replaced", async () => {
    const { result, save, onSaved } = setup();
    act(() => result.current.startEdit(FUND_B));
    act(() => result.current.setDraft((d) => ({ ...d, fund: "Beta Two" })));
    await act(() => result.current.saveEdit());
    expect(save).toHaveBeenCalledWith([FUND_A, { ...FUND_B, fund: "Beta Two" }]);
    expect(toastMock.success).toHaveBeenCalledWith("Fund updated");
    expect(onSaved).toHaveBeenCalledOnce();
    expect(result.current.editingCik).toBeNull();
  });

  it("rejects a non-https website and keeps editing", async () => {
    const { result, save } = setup();
    act(() => result.current.startEdit(FUND_A));
    act(() => result.current.setDraft((d) => ({ ...d, url: "http://insecure.example" })));
    await act(() => result.current.saveEdit());
    expect(save).not.toHaveBeenCalled();
    expect(toastMock.error).toHaveBeenCalledWith("Website URL must start with https://");
    expect(result.current.editingCik).toBe("1");
  });

  it("reports a failed save and keeps the editor open with the draft", async () => {
    const failing = vi.fn<(updated: HedgeFund[]) => Promise<void>>(async () => {
      throw new Error("disk full");
    });
    const { result, onSaved } = setup(failing);
    act(() => result.current.startEdit(FUND_A));
    act(() => result.current.setDraft({ ...result.current.draft, manager: "Edited Manager" }));
    await act(() => result.current.saveEdit());
    expect(toastMock.error).toHaveBeenCalledWith("disk full");
    expect(onSaved).not.toHaveBeenCalled();
    expect(result.current.editingCik).toBe(FUND_A.cik);
    expect(result.current.draft.manager).toBe("Edited Manager");
  });
});
