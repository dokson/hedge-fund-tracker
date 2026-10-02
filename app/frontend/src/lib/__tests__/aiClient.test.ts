import { afterEach, describe, expect, it, vi } from "vitest";

import { parseSSEEvent, runDueDiligenceStream, runPromiseScoreStream } from "../aiClient";

describe("parseSSEEvent", () => {
  it.each([
    ['{"type":"log","text":"Working"}', { type: "log", text: "Working" }],
    ['{"type":"result","data":[1,2]}', { type: "result", data: [1, 2] }],
    ['{"type":"error","message":"boom"}', { type: "error", message: "boom" }],
  ])("parses %s", (payload, expected) => {
    expect(parseSSEEvent(payload)).toEqual(expected);
  });

  it("supplies a fallback message for an error event without one", () => {
    const event = parseSSEEvent('{"type":"error"}');
    expect(event?.type).toBe("error");
    expect(event && event.type === "error" && event.message.length > 0).toBe(true);
  });

  it("returns null for malformed payloads instead of leaking undefined", () => {
    expect(parseSSEEvent("not json")).toBeNull();
    expect(parseSSEEvent("42")).toBeNull();
    expect(parseSSEEvent('{"type":"log"}')).toBeNull();
    expect(parseSSEEvent('{"type":"log","text":7}')).toBeNull();
    expect(parseSSEEvent('{"type":"unknown"}')).toBeNull();
  });
});

function stubSSEFetch(result: unknown) {
  const body = `data: ${JSON.stringify({ type: "result", data: result })}

`;
  const fetchMock = vi.fn<typeof fetch>(async () => new Response(body, { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function sentBody(fetchMock: ReturnType<typeof stubSSEFetch>): Record<string, unknown> {
  const body = fetchMock.mock.calls[0]?.[1]?.body;
  if (typeof body !== "string") throw new Error("expected a JSON string request body");
  return JSON.parse(body);
}

describe("AI stream requests", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends the selected provider id with a promise-score request", async () => {
    const fetchMock = stubSSEFetch([]);
    await runPromiseScoreStream("2026Q2", 10, "m1", "groq", () => {});
    expect(sentBody(fetchMock)).toMatchObject({ model_id: "m1", provider_id: "groq" });
  });

  it("sends an explicit null provider id when none is selected", async () => {
    const fetchMock = stubSSEFetch({ ticker: "XYZ" });
    await runDueDiligenceStream("XYZ", "2026Q2", undefined, "", () => {});
    expect(sentBody(fetchMock)).toMatchObject({ model_id: null, provider_id: null });
  });
});

describe("AI request errors", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubErrorFetch(status: number, body: unknown) {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async () => new Response(JSON.stringify(body), { status })),
    );
  }

  it("turns a validation-error list into readable text", async () => {
    stubErrorFetch(422, {
      detail: [{ loc: ["body", "top_n"], msg: "Input should be a valid integer", type: "x" }],
    });
    await expect(runPromiseScoreStream("2026Q2", 10, "m", "p", () => {})).rejects.toThrow(
      "body.top_n: Input should be a valid integer",
    );
  });

  it("keeps a plain string detail as the message", async () => {
    stubErrorFetch(400, { detail: "Unknown provider" });
    await expect(runDueDiligenceStream("XYZ", "2026Q2", "m", "p", () => {})).rejects.toThrow(
      "Unknown provider",
    );
  });

  it("falls back to the status when there is no detail", async () => {
    stubErrorFetch(500, {});
    await expect(runDueDiligenceStream("XYZ", "2026Q2", "m", "p", () => {})).rejects.toThrow(
      "Server error 500",
    );
  });
});
