import { afterEach, describe, expect, it, vi } from "vitest";

import * as aiClient from "../aiClient";
import { parseSSEEvent, runDueDiligenceStream, runPromiseScoreStream } from "../aiClient";

describe("parseSSEEvent", () => {
  it("parses a log event", () => {
    expect(parseSSEEvent('{"type":"log","text":"Working"}')).toEqual({
      type: "log",
      text: "Working",
    });
  });

  it("parses a result event, passing data through untouched", () => {
    expect(parseSSEEvent('{"type":"result","data":[1,2]}')).toEqual({
      type: "result",
      data: [1, 2],
    });
  });

  it("parses an error event", () => {
    expect(parseSSEEvent('{"type":"error","message":"boom"}')).toEqual({
      type: "error",
      message: "boom",
    });
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

  it("exposes only the streaming entry points", () => {
    expect(Object.keys(aiClient)).not.toContain("runPromiseScore");
    expect(Object.keys(aiClient)).not.toContain("runDueDiligence");
  });
});
