import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAssistantSpeech } from "@/hooks/use-assistant-speech";
import { createSpeechBus } from "@/lib/speech-bus";

const playback = vi.hoisted(() => ({
  enqueue: vi.fn(),
  playAll: vi.fn(),
  stop: vi.fn(),
  unlock: vi.fn(),
  resetLimit: vi.fn(),
  activeKey: null,
  isSpeaking: false,
  error: null as string | null,
}));

vi.mock("@/hooks/use-speech-playback", () => ({
  useSpeechPlayback: () => playback,
}));

beforeEach(() => {
  [
    playback.enqueue,
    playback.playAll,
    playback.stop,
    playback.unlock,
    playback.resetLimit,
  ].forEach((fn) => fn.mockReset());
});

function setup(enabled = true) {
  const bus = createSpeechBus();
  const hook = renderHook(
    (props: { enabled: boolean }) =>
      useAssistantSpeech({
        sessionId: "s-1",
        bus,
        enabled: props.enabled,
        speed: 1,
      }),
    { initialProps: { enabled } },
  );
  return { bus, ...hook };
}

describe("useAssistantSpeech", () => {
  it("reads streamed sentences while enabled", () => {
    const { bus } = setup();
    act(() => {
      bus.text("r1", "半分に");
      bus.text("r1", "絞ります。次。");
      bus.end();
    });
    expect(playback.enqueue.mock.calls).toEqual([
      ["r1", 0, "半分に絞ります。"],
      ["r1", 1, "次。"],
    ]);
  });

  it("does not read while disabled", () => {
    const { bus } = setup(false);
    act(() => {
      bus.text("r1", "半分です。");
      bus.end();
    });
    expect(playback.enqueue).not.toHaveBeenCalled();
  });

  it("silence skips the rest of the current response", () => {
    const { bus, result } = setup();
    act(() => bus.text("r1", "一。"));
    act(() => result.current.silence(false));
    act(() => {
      bus.text("r1", "二。");
      bus.end();
    });
    expect(playback.enqueue.mock.calls).toEqual([["r1", 0, "一。"]]);
    expect(playback.stop).toHaveBeenCalled();
  });

  it("silence(true) skips the next response when none has started", () => {
    const { bus, result } = setup();
    act(() => result.current.silence(true));
    act(() => {
      bus.text("r1", "一。");
      bus.end();
      bus.text("r2", "二。");
      bus.end();
    });
    expect(playback.enqueue.mock.calls).toEqual([["r2", 0, "二。"]]);
  });

  it("silence(true) is cleared by a response that ends without text", () => {
    const { bus, result } = setup();
    act(() => result.current.silence(true));
    act(() => bus.end());
    act(() => {
      bus.text("r2", "二。");
      bus.end();
    });
    expect(playback.enqueue.mock.calls).toEqual([["r2", 0, "二。"]]);
  });

  it("disabling stops playback and skips the response in progress", () => {
    const { bus, rerender } = setup();
    act(() => bus.text("r1", "一。"));
    rerender({ enabled: false });
    rerender({ enabled: true });
    act(() => {
      bus.text("r1", "二。");
      bus.end();
    });
    expect(playback.stop).toHaveBeenCalled();
    expect(playback.enqueue.mock.calls).toEqual([["r1", 0, "一。"]]);
  });

  it("enabling resets the daily limit message", () => {
    const { rerender } = setup(false);
    rerender({ enabled: true });
    expect(playback.resetLimit).toHaveBeenCalled();
  });

  it("playMessage unlocks and plays every sentence", () => {
    const { result } = setup(false);
    act(() => result.current.playMessage("r9", "一。二。"));
    expect(playback.unlock).toHaveBeenCalled();
    expect(playback.playAll).toHaveBeenCalledWith("r9", ["一。", "二。"]);
  });

  it("abort stops playback without reading the rest", () => {
    const { bus } = setup();
    act(() => {
      bus.text("r1", "一。途中");
      bus.abort();
    });
    expect(playback.enqueue.mock.calls).toEqual([["r1", 0, "一。"]]);
    expect(playback.stop).toHaveBeenCalled();
  });
});
