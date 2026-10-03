import { describe, expect, it, vi } from "vitest";
import { createSpeechBus } from "@/lib/speech-bus";

function listener() {
  return { onText: vi.fn(), onEnd: vi.fn(), onAbort: vi.fn() };
}

describe("createSpeechBus", () => {
  it("delivers keyed text and end to every listener", () => {
    const bus = createSpeechBus();
    const a = listener();
    const b = listener();
    bus.subscribe(a);
    bus.subscribe(b);

    bus.text("r1", "こんにちは");
    bus.end();

    expect(a.onText).toHaveBeenCalledWith("r1", "こんにちは");
    expect(b.onText).toHaveBeenCalledWith("r1", "こんにちは");
    expect(a.onEnd).toHaveBeenCalledTimes(1);
  });

  it("stops delivering after unsubscribe", () => {
    const bus = createSpeechBus();
    const l = listener();
    const unsubscribe = bus.subscribe(l);

    unsubscribe();
    bus.text("r1", "x");
    bus.end();

    expect(l.onText).not.toHaveBeenCalled();
    expect(l.onEnd).not.toHaveBeenCalled();
  });

  it("delivers abort to every listener", () => {
    const bus = createSpeechBus();
    const l = listener();
    bus.subscribe(l);

    bus.abort();

    expect(l.onAbort).toHaveBeenCalledTimes(1);
    expect(l.onEnd).not.toHaveBeenCalled();
  });
});
