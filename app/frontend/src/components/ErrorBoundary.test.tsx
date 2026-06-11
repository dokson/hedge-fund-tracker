/**
 * Tests for the route-level <ErrorBoundary>. A render crash anywhere in a page
 * must surface the fallback card instead of white-screening the app, and the
 * boundary must recover both via "Try again" and when resetKey (route) changes.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ErrorBoundary } from "./ErrorBoundary";

function Bomb({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error("kaboom");
  return <div>recovered content</div>;
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders children when nothing throws", () => {
    render(
      <ErrorBoundary resetKey="/a">
        <div>healthy content</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("healthy content")).toBeTruthy();
  });

  it("shows the fallback with the error detail when a child throws", () => {
    render(
      <ErrorBoundary resetKey="/a">
        <Bomb shouldThrow />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/something went wrong/i)).toBeTruthy();
    expect(screen.getByText(/kaboom/)).toBeTruthy();
  });

  it("recovers when 'Try again' is clicked", () => {
    let shouldThrow = true;
    const { rerender } = render(
      <ErrorBoundary resetKey="/a">
        <Bomb shouldThrow={shouldThrow} />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/something went wrong/i)).toBeTruthy();

    shouldThrow = false;
    rerender(
      <ErrorBoundary resetKey="/a">
        <Bomb shouldThrow={shouldThrow} />
      </ErrorBoundary>,
    );
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(screen.getByText("recovered content")).toBeTruthy();
  });

  it("resets automatically when resetKey changes (route navigation)", () => {
    const { rerender } = render(
      <ErrorBoundary resetKey="/a">
        <Bomb shouldThrow />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/something went wrong/i)).toBeTruthy();

    rerender(
      <ErrorBoundary resetKey="/b">
        <Bomb shouldThrow={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("recovered content")).toBeTruthy();
  });
});
