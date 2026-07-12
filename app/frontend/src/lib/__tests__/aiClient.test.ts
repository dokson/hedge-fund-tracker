import { describe, expect, it } from "vitest";

import { parseSSEEvent } from "../aiClient";

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
