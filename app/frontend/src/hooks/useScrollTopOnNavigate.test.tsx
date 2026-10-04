import { useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router";

import { useScrollTopOnNavigate } from "./useScrollTopOnNavigate";

const nav: { current: ReturnType<typeof useNavigate> | null } = { current: null };

function Probe() {
  const navigate = useNavigate();
  useEffect(() => {
    nav.current = navigate;
  }, [navigate]);
  useScrollTopOnNavigate();
  return null;
}

function navigate(to: string) {
  void nav.current?.(to);
}

function renderAt(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Probe />
    </MemoryRouter>,
  );
}

describe("useScrollTopOnNavigate", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("scrolls the window to the top when the path changes", () => {
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    renderAt("/latest");
    scrollTo.mockClear();

    act(() => {
      navigate("/quarterly");
    });

    expect(scrollTo).toHaveBeenCalledWith(0, 0);
  });

  it("leaves the scroll alone when the target carries a hash", () => {
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    renderAt("/latest");
    scrollTo.mockClear();

    act(() => {
      navigate("/learn#how-funds-are-selected");
    });

    expect(scrollTo).not.toHaveBeenCalled();
  });
});
