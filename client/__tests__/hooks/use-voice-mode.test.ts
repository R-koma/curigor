import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useVoiceMode } from "@/hooks/use-voice-mode";
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

function memoryStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (key) => map.get(key) ?? null,
    key: (index) => [...map.keys()][index] ?? null,
    removeItem: (key) => void map.delete(key),
    setItem: (key, value) => void map.set(key, value),
  };
}

beforeEach(() => {
  for (const fn of [
    playback.enqueue,
    playback.playAll,
    playback.stop,
    playback.unlock,
    playback.resetLimit,
  ]) {
    fn.mockReset();
  }
  vi.stubGlobal("localStorage", memoryStorage());
});

afterEach(() => vi.unstubAllGlobals());

function setup() {
  const bus = createSpeechBus();
  const hook = renderHook(() => useVoiceMode({ sessionId: "s-1", bus }));
  return { bus, ...hook };
}

describe("useVoiceMode", () => {
  it("reads nothing aloud while the mode is off", () => {
    const { bus } = setup();

    act(() => {
      bus.text("r1", "二分探索です。");
      bus.end();
    });

    expect(playback.enqueue).not.toHaveBeenCalled();
  });

  it("queues each sentence with the response key and its position", () => {
    const { bus, result } = setup();
    act(() => result.current.setEnabled(true));

    act(() => {
      bus.text("r1", "一つ目です。二つ");
      bus.text("r1", "目です");
      bus.end();
    });

    expect(playback.enqueue.mock.calls).toEqual([
      ["r1", 0, "一つ目です。"],
      ["r1", 1, "二つ目です"],
    ]);
  });

  it("numbers sentences from zero for each response", () => {
    const { bus, result } = setup();
    act(() => result.current.setEnabled(true));

    act(() => {
      bus.text("r1", "一。");
      bus.end();
      bus.text("r2", "二。");
      bus.end();
    });

    expect(playback.enqueue.mock.calls).toEqual([
      ["r1", 0, "一。"],
      ["r2", 0, "二。"],
    ]);
  });

  it("unlocks audio and resets the daily limit when turned on, and stops when turned off", () => {
    const { result } = setup();

    act(() => result.current.setEnabled(true));
    expect(playback.unlock).toHaveBeenCalled();
    expect(playback.resetLimit).toHaveBeenCalled();

    act(() => result.current.setEnabled(false));
    expect(playback.stop).toHaveBeenCalled();
  });

  it("does not create audio on interrupt while the mode is off", () => {
    const { result } = setup();

    act(() => result.current.interrupt());

    expect(playback.unlock).not.toHaveBeenCalled();
    expect(playback.stop).toHaveBeenCalled();
  });

  it("unlocks audio on interrupt while the mode is on", () => {
    const { result } = setup();
    act(() => result.current.setEnabled(true));
    playback.unlock.mockClear();

    act(() => result.current.interrupt());

    expect(playback.unlock).toHaveBeenCalled();
  });

  it("remembers the mode", () => {
    const first = setup();
    act(() => first.result.current.setEnabled(true));
    first.unmount();

    const second = setup();

    expect(second.result.current.enabled).toBe(true);
  });

  it("stays silent for the rest of a response that was interrupted mid-stream", () => {
    const { bus, result } = setup();
    act(() => result.current.setEnabled(true));
    act(() => bus.text("r1", "途中です。"));
    playback.enqueue.mockClear();

    act(() => result.current.interrupt());
    act(() => {
      bus.text("r1", "続きです。");
      bus.end();
    });

    expect(playback.enqueue).not.toHaveBeenCalled();
  });

  it("reads the next response after an interrupted one ended", () => {
    const { bus, result } = setup();
    act(() => result.current.setEnabled(true));
    act(() => bus.text("r1", "途中です。"));
    act(() => result.current.interrupt());
    act(() => bus.end());
    playback.enqueue.mockClear();

    act(() => {
      bus.text("r2", "次の応答です。");
      bus.end();
    });

    expect(playback.enqueue).toHaveBeenCalledWith("r2", 0, "次の応答です。");
  });

  it("does not silence the next response when stopped while idle", () => {
    const { bus, result } = setup();
    act(() => result.current.setEnabled(true));
    act(() => result.current.interrupt());

    act(() => {
      bus.text("r1", "次の応答です。");
      bus.end();
    });

    expect(playback.enqueue).toHaveBeenCalledWith("r1", 0, "次の応答です。");
  });

  it("skips the rest of a response that was already streaming when turned on", () => {
    const { bus, result } = setup();
    act(() => bus.text("r1", "途中から。"));

    act(() => result.current.setEnabled(true));
    act(() => {
      bus.text("r1", "残りです。");
      bus.end();
    });

    expect(playback.enqueue).not.toHaveBeenCalled();
  });

  it("drops a half-read response on abort and reads the next session's first reply", () => {
    const { bus, result } = setup();
    act(() => result.current.setEnabled(true));
    act(() => bus.text("r1", "途中で切れる文"));
    playback.stop.mockClear();
    playback.enqueue.mockClear();

    act(() => bus.abort());
    expect(playback.stop).toHaveBeenCalled();

    act(() => result.current.interrupt());
    act(() => {
      bus.text("r2", "新しいセッションの最初の応答です。");
      bus.end();
    });

    expect(playback.enqueue.mock.calls).toEqual([
      ["r2", 0, "新しいセッションの最初の応答です。"],
    ]);
  });

  it("plays a whole message on request even while the mode is off", () => {
    const { result } = setup();

    act(() => result.current.playMessage("m1", "一つ目です。二つ目です。"));

    expect(playback.unlock).toHaveBeenCalled();
    expect(playback.playAll).toHaveBeenCalledWith("m1", [
      "一つ目です。",
      "二つ目です。",
    ]);
  });

  it("silences the rest of a streaming response when another message is played", () => {
    const { bus, result } = setup();
    act(() => result.current.setEnabled(true));
    act(() => bus.text("r1", "途中です。"));

    act(() => result.current.playMessage("old", "昔の応答。"));
    playback.enqueue.mockClear();
    act(() => {
      bus.text("r1", "続きです。");
      bus.end();
    });

    expect(playback.enqueue).not.toHaveBeenCalled();
  });

  it("stops playback on unmount", () => {
    const { unmount } = setup();

    unmount();

    expect(playback.stop).toHaveBeenCalled();
  });
});
