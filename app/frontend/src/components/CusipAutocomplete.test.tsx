/**
 * Regression tests for the inline-callback infinite-loop bug.
 *
 * Symptom: clicking on /database froze the whole app. Root cause was that
 * CusipAutocomplete had `onValidChange` in its useEffect deps. Callers
 * (DatabaseOperations) pass an inline arrow which changes identity every
 * render → the effect re-fires → setState in parent → re-render → new
 * identity → effect again → main-thread saturation. React doesn't flag this
 * as "Maximum update depth exceeded" because the deps technically change
 * each tick, so the silent freeze had no console error.
 *
 * The fix stabilises the callback via a ref. These tests assert that
 * passing an unstable callback doesn't trigger a runaway loop.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { render, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import CusipAutocomplete from "./CusipAutocomplete";
import { clearCache } from "@/lib/dataService";

const STOCKS_CSV = `"CUSIP","Ticker","Company","Industry"
"037833100","AAPL","Apple Inc","Consumer Electronics"
`;
const HIERARCHY_CSV = `"Sector","Industry"
"Technology","Consumer Electronics"
`;

function csvResponse(body: string) {
  return { ok: true, text: async () => body } as Response;
}

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("CusipAutocomplete — inline-callback stability", () => {
  beforeEach(() => {
    clearCache();
    vi.restoreAllMocks();
    vi.spyOn(global, "fetch").mockImplementation((async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : (input as URL).toString();
      if (url.includes("stocks.csv")) return csvResponse(STOCKS_CSV);
      if (url.includes("sector_hierarchy.csv")) return csvResponse(HIERARCHY_CSV);
      throw new Error(`Unexpected fetch: ${url}`);
    }) as unknown as typeof fetch);
  });

  it("does not re-invoke onValidChange when the parent re-creates the callback identity each render", async () => {
    // Simulate the bug-trigger pattern from DatabaseOperations: a parent that
    // owns no dependency on the child's value, but defines onValidChange as
    // an inline arrow (new identity per render).
    const validChangeCalls = { count: 0 };

    function Parent() {
      const [_touched, setTouched] = useState(0);
      void _touched;
      return (
        <div>
          <button onClick={() => setTouched((n) => n + 1)}>force-render</button>
          <CusipAutocomplete
            value=""
            onChange={() => {}}
            onValidChange={(v) => {
              validChangeCalls.count += 1;
              // Don't setState here — we're isolating whether the autocomplete
              // alone fires more often than necessary.
              void v;
            }}
          />
        </div>
      );
    }

    const { getByText } = renderWithQuery(<Parent />);

    // Wait for the initial fetch to resolve and the effect to flush.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    const baseline = validChangeCalls.count;

    // Force several parent renders. Pre-fix code would re-invoke
    // onValidChange every render because the callback identity changed and
    // was in the effect deps.
    for (let i = 0; i < 5; i++) {
      await act(async () => {
        getByText("force-render").click();
      });
    }

    // Allow microtasks to drain.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    // The effect should only fire on isValid changes, not on parent re-renders.
    // We tolerate 1-2 calls (initial mount + maybe a single mounting tick) but
    // not 5+ which would indicate the inline-callback dep loop is back.
    expect(validChangeCalls.count - baseline).toBeLessThanOrEqual(1);
  });
});
