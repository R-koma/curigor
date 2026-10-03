import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useVoiceMode } from "@/hooks/use-voice-mode";
import { createSpeechBus } from "@/lib/speech-bus";

const playback = vi.hoisted(() => ({
  enqueue: vi.fn(),
  stop: vi.fn(),
  unlock: vi.fn(),
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
  playback.enqueue.mockReset();
  playback.stop.mockReset();
  playback.unlock.mockReset();
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
      bus.text("二分探索です。");
      bus.end();
    });

    expect(playback.enqueue).not.toHaveBeenCalled();
  });

  it("reads each finished sentence and the remainder when on", () => {
    const { bus, result } = setup();
    act(() => result.current.setEnabled(true));

    act(() => {
      bus.text("一つ目です。二つ");
      bus.text("目です");
      bus.end();
    });

    expect(playback.enqueue.mock.calls.map((c) => c[0])).toEqual([
      "一つ目です。",
      "二つ目です",
    ]);
  });

  it("unlocks audio when turned on and stops when turned off", () => {
    const { result } = setup();

    act(() => result.current.setEnabled(true));
    expect(playback.unlock).toHaveBeenCalled();

    act(() => result.current.setEnabled(false));
    expect(playback.stop).toHaveBeenCalled();
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
    act(() => bus.text("途中です。"));
    playback.enqueue.mockClear();

    act(() => result.current.interrupt());
    act(() => {
      bus.text("続きです。");
      bus.end();
    });

    expect(playback.enqueue).not.toHaveBeenCalled();
  });

  it("reads the next response after an interrupted one ended", () => {
    const { bus, result } = setup();
    act(() => result.current.setEnabled(true));
    act(() => bus.text("途中です。"));
    act(() => result.current.interrupt());
    act(() => bus.end());
    playback.enqueue.mockClear();

    act(() => {
      bus.text("次の応答です。");
      bus.end();
    });

    expect(playback.enqueue).toHaveBeenLastCalledWith("次の応答です。");
  });

  it("does not silence the next response when stopped while idle", () => {
    const { bus, result } = setup();
    act(() => result.current.setEnabled(true));
    act(() => result.current.interrupt());

    act(() => {
      bus.text("次の応答です。");
      bus.end();
    });

    expect(playback.enqueue).toHaveBeenCalledWith("次の応答です。");
  });

  it("skips the rest of a response that was already streaming when turned on", () => {
    const { bus, result } = setup();
    act(() => bus.text("途中から。"));

    act(() => result.current.setEnabled(true));
    act(() => {
      bus.text("残りです。");
      bus.end();
    });

    expect(playback.enqueue).not.toHaveBeenCalled();
  });

  it("drops a half-read response on abort and reads the next session's first reply", () => {
    const { bus, result } = setup();
    act(() => result.current.setEnabled(true));
    act(() => bus.text("途中で切れる文"));
    playback.stop.mockClear();
    playback.enqueue.mockClear();

    act(() => bus.abort());
    expect(playback.stop).toHaveBeenCalled();

    act(() => result.current.interrupt());
    act(() => {
      bus.text("新しいセッションの最初の応答です。");
      bus.end();
    });

    expect(playback.enqueue).toHaveBeenCalledTimes(1);
    expect(playback.enqueue).toHaveBeenCalledWith(
      "新しいセッションの最初の応答です。",
    );
  });

  it("stops playback on unmount", () => {
    const { unmount } = setup();

    unmount();

    expect(playback.stop).toHaveBeenCalled();
  });
});
