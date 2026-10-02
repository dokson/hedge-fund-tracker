import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { QueryState } from "./QueryState";

describe("QueryState", () => {
  it("renders the children when there is no error", () => {
    render(
      <QueryState isError={false} error={null}>
        <p>content</p>
      </QueryState>,
    );
    expect(screen.getByText("content")).toBeDefined();
  });

  it("replaces the children with an alert carrying the error message", () => {
    render(
      <QueryState isError error={new Error("Failed to fetch x: 500")} title="Could not load data">
        <p>content</p>
      </QueryState>,
    );
    expect(screen.queryByText("content")).toBeNull();
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("Could not load data");
    expect(alert.textContent).toContain("Failed to fetch x: 500");
  });
});
