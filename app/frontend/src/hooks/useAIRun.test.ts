import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const getModelsMock = vi.hoisted(() =>
  vi.fn<() => Promise<{ id: string; description: string }[]>>(),
);
vi.mock("@/lib/dataService", () => ({ getModels: getModelsMock }));
vi.mock("sonner", () => ({ toast: { success: vi.fn<() => void>(), error: vi.fn<() => void>() } }));

import { useAIRun, type AIRunContext } from "./useAIRun";

function deferred<T>() {
  let resolve: (v: T) => void = () => undefined;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

describe("useAIRun", () => {
  afterEach(() => getModelsMock.mockReset());

  it("ignores a superseded run's result and keeps loading for the newer one", async () => {
    getModelsMock.mockResolvedValue([]);
    const first = deferred<string>();
    const second = deferred<string>();
    const execute = vi
      .fn<(ctx: AIRunContext) => Promise<string>>()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    const { result } = renderHook(() => useAIRun({ execute }));

    let runA: Promise<void> = Promise.resolve();
    let runB: Promise<void> = Promise.resolve();
    await act(async () => {
      runA = result.current.run();
      await Promise.resolve();
    });
    await act(async () => {
      runB = result.current.run();
      await Promise.resolve();
    });
    await act(async () => {
      first.resolve("stale");
      await runA;
    });
    expect(result.current.result).toBeNull();
    expect(result.current.loading).toBe(true);

    await act(async () => {
      second.resolve("fresh");
      await runB;
    });
    expect(result.current.result).toBe("fresh");
    expect(result.current.loading).toBe(false);
  });

  it("does not start the request when aborted while models load", async () => {
    const models = deferred<{ id: string; description: string }[]>();
    getModelsMock.mockReturnValue(models.promise);
    const execute = vi.fn<(ctx: AIRunContext) => Promise<string>>(async () => "x");
    const { result, unmount } = renderHook(() => useAIRun({ execute }));
    let run: Promise<void> = Promise.resolve();
    act(() => {
      run = result.current.run();
    });
    unmount();
    models.resolve([]);
    await run;
    expect(execute).not.toHaveBeenCalled();
  });
});
