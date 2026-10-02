import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

const fetchMock = vi.hoisted(() => vi.fn<(quarter: string) => Promise<unknown[] | null>>());
const runMock = vi.hoisted(() =>
  vi.fn<(quarter: string, onProgress?: unknown, filter?: Set<string>) => Promise<unknown[]>>(),
);

vi.mock("@/lib/dataService", () => ({
  fetchQuarterAnalysis: fetchMock,
  runQuarterAnalysis: runMock,
}));

import { quarterAnalysisKey, useQuarterAnalysis } from "./useQuarterAnalysis";

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

const ROW = { ticker: "AAA" };

describe("useQuarterAnalysis", () => {
  afterEach(() => {
    fetchMock.mockReset();
    runMock.mockReset();
  });

  it("uses the backend frame when available", async () => {
    fetchMock.mockResolvedValue([ROW]);
    const client = new QueryClient();
    const { result } = renderHook(() => useQuarterAnalysis("2026Q2"), {
      wrapper: wrapper(client),
    });
    await waitFor(() => expect(result.current.data).toEqual([ROW]));
    expect(runMock).not.toHaveBeenCalled();
  });

  it("falls back to the client pipeline when the backend has no frame", async () => {
    fetchMock.mockResolvedValue(null);
    runMock.mockResolvedValue([ROW]);
    const client = new QueryClient();
    const { result } = renderHook(() => useQuarterAnalysis("2026Q2"), {
      wrapper: wrapper(client),
    });
    await waitFor(() => expect(result.current.data).toEqual([ROW]));
  });

  it("runs the client pipeline directly under its own key for a fund filter", async () => {
    runMock.mockResolvedValue([ROW]);
    const client = new QueryClient();
    const filter = new Set(["B", "A"]);
    const { result } = renderHook(() => useQuarterAnalysis("2026Q2", { fundFilter: filter }), {
      wrapper: wrapper(client),
    });
    await waitFor(() => expect(result.current.data).toEqual([ROW]));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(runMock).toHaveBeenCalledWith("2026Q2", undefined, filter);
    expect(quarterAnalysisKey("2026Q2", filter)).toEqual(["quarterAnalysis", "2026Q2", "A,B"]);
  });

  it("stays idle without a quarter", () => {
    const client = new QueryClient();
    const { result } = renderHook(() => useQuarterAnalysis(undefined), {
      wrapper: wrapper(client),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
