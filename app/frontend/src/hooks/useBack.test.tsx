import { fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, useLocation } from "react-router";
import { describe, expect, it } from "vitest";

import { useBack } from "./useBack";

function Page({ fallback }: { fallback: string }) {
  const back = useBack(fallback);
  const { pathname } = useLocation();
  return (
    <>
      <p data-testid="path">{pathname}</p>
      <Link to="/stock/NVDA">open stock</Link>
      <button type="button" onClick={back}>
        back
      </button>
    </>
  );
}

const renderAt = (entry: string) =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Page fallback="/stocks" />
    </MemoryRouter>,
  );

describe("useBack", () => {
  it("goes to the fallback when the app was entered on this page", () => {
    renderAt("/stock/NVDA");
    fireEvent.click(screen.getByRole("button", { name: "back" }));
    expect(screen.getByTestId("path").textContent).toBe("/stocks");
  });

  it("returns to the page the visitor came from, not to the fallback", () => {
    renderAt("/funds/Herald");
    fireEvent.click(screen.getByRole("link", { name: "open stock" }));
    expect(screen.getByTestId("path").textContent).toBe("/stock/NVDA");

    fireEvent.click(screen.getByRole("button", { name: "back" }));
    expect(screen.getByTestId("path").textContent).toBe("/funds/Herald");
  });
});
