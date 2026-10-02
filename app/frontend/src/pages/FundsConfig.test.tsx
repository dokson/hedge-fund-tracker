import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { HedgeFund } from "@/lib/dataService";

const saveMock = vi.hoisted(() => vi.fn<(content: string, path: string) => Promise<void>>());
vi.mock("sonner", () => ({
  toast: { success: vi.fn<() => void>(), error: vi.fn<() => void>() },
}));
vi.mock("@/lib/dataService", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/dataService")>();
  const active: HedgeFund[] = [
    { cik: "1", fund: "Alpha", manager: "Ann", denomination: "Alpha LP", ciks: "1", url: "" },
  ];
  const excluded: HedgeFund[] = [
    { cik: "9", fund: "Omega", manager: "Oz", denomination: "Omega LP", ciks: "9", url: "" },
  ];
  return {
    ...actual,
    getHedgeFunds: vi.fn<() => Promise<HedgeFund[]>>(async () => active),
    getExcludedHedgeFunds: vi.fn<() => Promise<HedgeFund[]>>(async () => excluded),
    saveFileToDisk: saveMock,
  };
});

import FundsConfig from "./FundsConfig";

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <TooltipProvider>
        <MemoryRouter>
          <FundsConfig />
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

describe("FundsConfig", () => {
  afterEach(() => saveMock.mockReset());

  it("links each tab to the panel it controls", () => {
    renderPage();
    const tab = screen.getByRole("tab", { name: /Active Funds/ });
    expect(tab.getAttribute("aria-controls")).toBe(screen.getByRole("tabpanel").id);
  });

  it("switches to the excluded list", async () => {
    renderPage();
    fireEvent.mouseDown(screen.getByRole("tab", { name: /Excluded/ }));
    const table = await screen.findByRole("table", { name: "Excluded funds" });
    expect(within(table).getByText("Omega")).toBeDefined();
  });

  it("adds a fund through the dialog", async () => {
    saveMock.mockResolvedValue(undefined);
    renderPage();
    await screen.findByRole("table", { name: "Active funds" });
    fireEvent.click(screen.getByRole("button", { name: /Add Fund/ }));
    fireEvent.change(screen.getByLabelText("CIK"), { target: { value: "42x" } });
    fireEvent.change(screen.getByLabelText("Fund Name"), { target: { value: " Gamma " } });
    fireEvent.change(screen.getByLabelText("Manager"), { target: { value: "Gil" } });
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Add Fund" }));
    await waitFor(() => expect(saveMock).toHaveBeenCalledOnce());
    const [csv, path] = saveMock.mock.calls[0] ?? ["", ""];
    expect(path).toBe("hedge_funds.csv");
    expect(csv).toContain("Gamma");
    expect(csv).toContain("42");
  });
});
