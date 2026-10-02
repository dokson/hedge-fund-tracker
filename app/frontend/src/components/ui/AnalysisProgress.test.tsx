import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnalysisProgress } from "./AnalysisProgress";

describe("AnalysisProgress", () => {
  it("shows an indeterminate loader without a bar while no progress was reported", () => {
    render(<AnalysisProgress msg="" pct={0} />);
    expect(screen.getByText("Loading analysis…")).toBeDefined();
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("hides a 0% bar even when a stale message is present", () => {
    render(<AnalysisProgress msg="Fetching holdings" pct={0} />);
    expect(screen.getByText("Loading analysis…")).toBeDefined();
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("shows the message and the bar once progress is reported", () => {
    render(<AnalysisProgress msg="Fetching holdings" pct={40} />);
    expect(screen.getByText("Fetching holdings")).toBeDefined();
    expect(screen.getByRole("progressbar")).toBeDefined();
  });
});
