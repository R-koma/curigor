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
  hold: vi.fn(),
  release: vi.fn(),
  discardHeld: vi.fn(),
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
    playback.hold,
    playback.release,
    playback.discardHeld,
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

  it("interrupt holds playback and keeps reading the streamed rest", () => {
    const { bus, result } = setup();
    act(() => bus.text("r1", "一。"));
    act(() => result.current.interrupt(false));
    act(() => {
      bus.text("r1", "二。");
      bus.end();
    });
    expect(playback.hold).toHaveBeenCalledTimes(1);
    expect(playback.stop).not.toHaveBeenCalled();
    expect(playback.enqueue.mock.calls).toEqual([
      ["r1", 0, "一。"],
      ["r1", 1, "二。"],
    ]);
  });

  it("interrupt is idempotent while held", () => {
    const { bus, result } = setup();
    act(() => bus.text("r1", "一。"));
    act(() => {
      result.current.interrupt(false);
      result.current.interrupt(true);
    });
    expect(playback.hold).toHaveBeenCalledTimes(1);
  });

  it("resumeInterrupted releases the hold once", () => {
    const { bus, result } = setup();
    act(() => bus.text("r1", "一。"));
    act(() => result.current.interrupt(false));
    let first = false;
    let second = true;
    act(() => {
      first = result.current.resumeInterrupted();
      second = result.current.resumeInterrupted();
    });
    expect(first).toBe(true);
    expect(second).toBe(false);
    expect(playback.release).toHaveBeenCalledTimes(1);
  });

  it("discardInterrupted skips the rest of the held response", () => {
    const { bus, result } = setup();
    act(() => bus.text("r1", "一。"));
    act(() => result.current.interrupt(false));
    act(() => result.current.discardInterrupted());
    act(() => {
      bus.text("r1", "二。");
      bus.end();
    });
    expect(playback.discardHeld).toHaveBeenCalled();
    expect(playback.enqueue.mock.calls).toEqual([["r1", 0, "一。"]]);
    expect(result.current.resumeInterrupted()).toBe(false);
  });

  it("holds the upcoming response when interrupted while thinking", () => {
    const { bus, result } = setup();
    act(() => result.current.interrupt(true));
    act(() => {
      bus.text("r1", "一。");
      bus.end();
    });
    expect(playback.discardHeld).not.toHaveBeenCalled();
    expect(playback.enqueue.mock.calls).toEqual([["r1", 0, "一。"]]);
    let resumed = false;
    act(() => {
      resumed = result.current.resumeInterrupted();
    });
    expect(resumed).toBe(true);
  });

  it("discardInterrupted skips an upcoming response that has not started", () => {
    const { bus, result } = setup();
    act(() => result.current.interrupt(true));
    act(() => result.current.discardInterrupted());
    act(() => {
      bus.text("r1", "一。");
      bus.end();
      bus.text("r2", "二。");
      bus.end();
    });
    expect(playback.enqueue.mock.calls).toEqual([["r2", 0, "二。"]]);
  });

  it("a newer response drops the hold of an older one", () => {
    const { bus, result } = setup();
    act(() => bus.text("r1", "一。"));
    act(() => result.current.interrupt(false));
    act(() => {
      bus.end();
      bus.text("r2", "二。");
    });
    expect(playback.discardHeld).toHaveBeenCalled();
    expect(playback.enqueue.mock.calls.at(-1)).toEqual(["r2", 0, "二。"]);
    expect(result.current.resumeInterrupted()).toBe(false);
  });

  it("playMessage and abort drop the hold", () => {
    const { bus, result } = setup();
    act(() => bus.text("r1", "一。"));
    act(() => result.current.interrupt(false));
    act(() => result.current.playMessage("r1", "一。"));
    expect(result.current.resumeInterrupted()).toBe(false);

    act(() => bus.text("r2", "二。"));
    act(() => result.current.interrupt(false));
    act(() => bus.abort());
    expect(result.current.resumeInterrupted()).toBe(false);
  });

  it("disabling drops the hold", () => {
    const { bus, result, rerender } = setup();
    act(() => bus.text("r1", "一。"));
    act(() => result.current.interrupt(false));
    rerender({ enabled: false });
    expect(result.current.resumeInterrupted()).toBe(false);
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
