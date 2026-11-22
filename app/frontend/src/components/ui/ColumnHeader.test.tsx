import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ColumnHeader } from "./ColumnHeader";
import { APP_STATUS_ID } from "@/lib/announce";

function renderHeader(active: boolean, direction: "asc" | "desc") {
  render(
    <>
      <div id={APP_STATUS_ID} role="status" />
      <table>
        <thead>
          <tr>
            <ColumnHeader label="Value" sort={{ active, direction, onToggle: () => {} }} />
          </tr>
        </thead>
      </table>
    </>,
  );
}

describe("ColumnHeader sort announcement", () => {
  afterEach(() => vi.useRealTimers());

  it("announces the direction the click leads to, not the current one", () => {
    vi.useFakeTimers();
    renderHeader(true, "desc");
    fireEvent.click(screen.getByRole("button", { name: "Value" }));
    vi.runAllTimers();
    const spoken = screen.getByRole("status").textContent ?? "";
    expect(spoken).toMatch(/Value/);
    expect(spoken).toMatch(/ascending/);
  });

  it("announces descending when another column is picked, whatever its last direction", () => {
    vi.useFakeTimers();
    renderHeader(false, "asc");
    fireEvent.click(screen.getByRole("button", { name: "Value" }));
    vi.runAllTimers();
    const spoken = screen.getByRole("status").textContent ?? "";
    expect(spoken).toMatch(/Value/);
    expect(spoken).toMatch(/descending/);
  });
});
