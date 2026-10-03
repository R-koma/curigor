import { describe, expect, it, vi } from "vitest";
import { createSpeechBus } from "@/lib/speech-bus";

describe("createSpeechBus", () => {
  it("delivers text and end to every listener", () => {
    const bus = createSpeechBus();
    const a = { onText: vi.fn(), onEnd: vi.fn(), onAbort: vi.fn() };
    const b = { onText: vi.fn(), onEnd: vi.fn(), onAbort: vi.fn() };
    bus.subscribe(a);
    bus.subscribe(b);

    bus.text("こんにちは");
    bus.end();

    expect(a.onText).toHaveBeenCalledWith("こんにちは");
    expect(b.onText).toHaveBeenCalledWith("こんにちは");
    expect(a.onEnd).toHaveBeenCalledTimes(1);
  });

  it("stops delivering after unsubscribe", () => {
    const bus = createSpeechBus();
    const listener = { onText: vi.fn(), onEnd: vi.fn(), onAbort: vi.fn() };
    const unsubscribe = bus.subscribe(listener);

    unsubscribe();
    bus.text("x");
    bus.end();

    expect(listener.onText).not.toHaveBeenCalled();
    expect(listener.onEnd).not.toHaveBeenCalled();
  });

  it("delivers abort to every listener", () => {
    const bus = createSpeechBus();
    const listener = { onText: vi.fn(), onEnd: vi.fn(), onAbort: vi.fn() };
    bus.subscribe(listener);

    bus.abort();

    expect(listener.onAbort).toHaveBeenCalledTimes(1);
    expect(listener.onEnd).not.toHaveBeenCalled();
  });
});
