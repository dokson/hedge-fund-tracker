import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { SmartScoreBadge } from "./SmartScoreBadge";

describe("SmartScoreBadge", () => {
  it("renders the score with one decimal and the /10 scale", () => {
    const { container } = render(<SmartScoreBadge score={8.6} />);
    expect(container.textContent).toContain("8.6");
    expect(container.textContent).toContain("/10");
  });

  it("uses the positive tone for high scores", () => {
    const { container } = render(<SmartScoreBadge score={9.1} />);
    expect((container.firstElementChild as HTMLElement).className).toContain("positive");
  });

  it("uses the negative tone for low scores", () => {
    const { container } = render(<SmartScoreBadge score={2.0} />);
    expect((container.firstElementChild as HTMLElement).className).toContain("negative");
  });

  it("uses the neutral tone for mid scores", () => {
    const { container } = render(<SmartScoreBadge score={5.5} />);
    expect((container.firstElementChild as HTMLElement).className).toContain("amber");
  });
});
