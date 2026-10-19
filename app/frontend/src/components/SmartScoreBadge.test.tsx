import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { SmartScoreBadge } from "./SmartScoreBadge";

describe("SmartScoreBadge", () => {
  it.each([
    [9.1, "positive"],
    [5.5, "warning"],
    [2.0, "negative"],
  ])("tones a %d score as %s", (score, tone) => {
    const { container } = render(<SmartScoreBadge score={score} />);
    expect((container.firstElementChild as HTMLElement).className).toContain(tone);
  });
});
