import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  MAX_CACHED_RESPONSES,
  SPEECH_FAILED_MESSAGE,
  SPEECH_INTERRUPTED_MESSAGE,
  SPEECH_LIMIT_MESSAGE,
  useSpeechPlayback,
} from "@/hooks/use-speech-playback";
import { SpeechError, synthesizeSpeech } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, synthesizeSpeech: vi.fn() };
});

const mockSynth = vi.mocked(synthesizeSpeech);

class FakeSource {
  static autoEnd = false;
  buffer: { id: number } | null = null;
  onended: (() => void) | null = null;
  connect = vi.fn();
  start = vi.fn(() => {
    if (FakeSource.autoEnd) queueMicrotask(() => this.onended?.());
  });
  stop = vi.fn(() => this.onended?.());
}

class FakeAudioContext {
  static sources: FakeSource[] = [];
  static instances: FakeAudioContext[] = [];
  static initialState: AudioContextState = "running";
  static resumable = false;
  state: AudioContextState = FakeAudioContext.initialState;
  destination = {};
  resume = vi.fn(async () => {
    if (FakeAudioContext.resumable) this.state = "running";
  });
  close = vi.fn(async () => {});
  decodeAudioData = vi.fn(async (data: ArrayBuffer) => ({
    id: new Uint8Array(data)[0],
  }));
  createBufferSource = vi.fn(() => {
    const source = new FakeSource();
    FakeAudioContext.sources.push(source);
    return source as unknown as AudioBufferSourceNode;
  });

  constructor() {
    FakeAudioContext.instances.push(this);
  }
}

const byLength = async (_id: string, text: string) =>
  new Uint8Array([text.length]).buffer;

beforeEach(() => {
  FakeSource.autoEnd = false;
  FakeAudioContext.sources = [];
  FakeAudioContext.instances = [];
  FakeAudioContext.initialState = "running";
  FakeAudioContext.resumable = false;
  mockSynth.mockReset();
  mockSynth.mockImplementation(byLength);
  vi.stubGlobal("AudioContext", FakeAudioContext);
});

afterEach(() => vi.unstubAllGlobals());

function setup(sessionId: string | null = "s-1") {
  const hook = renderHook(
    ({ sessionId }: { sessionId: string | null }) =>
      useSpeechPlayback({ sessionId }),
    { initialProps: { sessionId } },
  );
  act(() => hook.result.current.unlock());
  return hook;
}

describe("useSpeechPlayback", () => {
  it("plays sentences in order and prefetches only the next one", async () => {
    const { result } = setup();

    act(() => {
      result.current.enqueue("r1", 0, "あ。");
      result.current.enqueue("r1", 1, "いい。");
      result.current.enqueue("r1", 2, "ううう。");
    });

    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    expect(mockSynth).toHaveBeenCalledTimes(2);
    expect(result.current.activeKey).toBe("r1");
    expect(result.current.isSpeaking).toBe(true);

    act(() => FakeAudioContext.sources[0].onended?.());
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(2));

    act(() => FakeAudioContext.sources[1].onended?.());
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(3));
    act(() => FakeAudioContext.sources[2].onended?.());

    expect(FakeAudioContext.sources.map((s) => s.buffer?.id)).toEqual([
      2, 3, 4,
    ]);
    await waitFor(() => expect(result.current.activeKey).toBeNull());
  });

  it("decodes a copy so the kept audio stays usable", async () => {
    const { result } = setup();

    act(() => result.current.enqueue("r1", 0, "あ。"));
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));

    const original = await mockSynth.mock.results[0].value;
    const decoded =
      FakeAudioContext.instances[0].decodeAudioData.mock.calls[0][0];
    expect(decoded).not.toBe(original);
    expect(new Uint8Array(decoded)).toEqual(new Uint8Array(original));
  });

  it("stops the sound, aborts pending requests and drops the queue", async () => {
    const { result } = setup();
    act(() => {
      result.current.enqueue("r1", 0, "あ。");
      result.current.enqueue("r1", 1, "いい。");
    });
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    const signal = mockSynth.mock.calls[0][2] as AbortSignal;

    act(() => result.current.stop());

    expect(FakeAudioContext.sources[0].stop).toHaveBeenCalled();
    expect(signal.aborted).toBe(true);
    expect(result.current.activeKey).toBeNull();
    await act(async () => {
      await Promise.resolve();
    });
    expect(FakeAudioContext.sources).toHaveLength(1);
  });

  it("requests a sentence again when it was stopped before arriving", async () => {
    mockSynth.mockImplementationOnce(
      (_id, _text, signal) =>
        new Promise((_resolve, reject) => {
          signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
        }),
    );
    const { result } = setup();

    act(() => result.current.enqueue("r1", 0, "あ。"));
    act(() => result.current.stop());
    act(() => result.current.playAll("r1", ["あ。"]));

    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    expect(mockSynth).toHaveBeenCalledTimes(2);
  });

  it("replays a response from the kept audio without requesting it again", async () => {
    FakeSource.autoEnd = true;
    const { result } = setup();
    act(() => {
      result.current.enqueue("r1", 0, "あ。");
      result.current.enqueue("r1", 1, "いい。");
    });
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(2));
    await waitFor(() => expect(result.current.activeKey).toBeNull());

    act(() => result.current.playAll("r1", ["あ。", "いい。"]));

    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(4));
    expect(mockSynth).toHaveBeenCalledTimes(2);
    expect(FakeAudioContext.sources.map((s) => s.buffer?.id)).toEqual([
      2, 3, 2, 3,
    ]);
  });

  it("stops the current playback before replaying another response", async () => {
    const { result } = setup();
    act(() => {
      result.current.enqueue("live", 0, "あ。");
      result.current.enqueue("live", 1, "いい。");
    });
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));

    act(() => result.current.playAll("old", ["ううう。"]));

    expect(FakeAudioContext.sources[0].stop).toHaveBeenCalled();
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(2));
    expect(result.current.activeKey).toBe("old");
  });

  it("forgets the oldest response beyond the keeping limit", async () => {
    FakeSource.autoEnd = true;
    const { result } = setup();
    for (let k = 0; k <= MAX_CACHED_RESPONSES; k++) {
      act(() => result.current.enqueue(`r${k}`, 0, "あ。"));
    }
    await waitFor(() =>
      expect(FakeAudioContext.sources).toHaveLength(MAX_CACHED_RESPONSES + 1),
    );
    const calls = mockSynth.mock.calls.length;

    act(() => result.current.playAll(`r${MAX_CACHED_RESPONSES}`, ["あ。"]));
    await waitFor(() =>
      expect(FakeAudioContext.sources).toHaveLength(MAX_CACHED_RESPONSES + 2),
    );
    expect(mockSynth.mock.calls.length).toBe(calls);

    act(() => result.current.playAll("r0", ["あ。"]));
    await waitFor(() =>
      expect(FakeAudioContext.sources).toHaveLength(MAX_CACHED_RESPONSES + 3),
    );
    expect(mockSynth.mock.calls.length).toBe(calls + 1);
  });

  it("skips a sentence that fails and reports it", async () => {
    mockSynth.mockImplementationOnce(async () => {
      throw new Error("boom");
    });
    const { result } = setup();

    act(() => {
      result.current.enqueue("r1", 0, "あ。");
      result.current.enqueue("r1", 1, "いい。");
    });

    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    expect(FakeAudioContext.sources[0].buffer?.id).toBe(3);
    expect(result.current.error).toBe(SPEECH_FAILED_MESSAGE);
  });

  it("stops requesting after the daily limit", async () => {
    mockSynth.mockImplementationOnce(async () => {
      throw new SpeechError(429);
    });
    const { result } = setup();
    act(() => {
      result.current.enqueue("r1", 0, "あ。");
      result.current.enqueue("r1", 1, "いい。");
    });
    await waitFor(() =>
      expect(result.current.error).toBe(SPEECH_LIMIT_MESSAGE),
    );
    const calls = mockSynth.mock.calls.length;

    act(() => result.current.enqueue("r2", 0, "ううう。"));

    expect(mockSynth.mock.calls.length).toBe(calls);
    expect(FakeAudioContext.sources).toHaveLength(0);
  });

  it("still replays kept audio after the daily limit", async () => {
    FakeSource.autoEnd = true;
    const { result } = setup();
    act(() => result.current.enqueue("r1", 0, "あ。"));
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    mockSynth.mockImplementationOnce(async () => {
      throw new SpeechError(429);
    });
    act(() => result.current.enqueue("r2", 0, "いい。"));
    await waitFor(() =>
      expect(result.current.error).toBe(SPEECH_LIMIT_MESSAGE),
    );

    act(() => result.current.playAll("r1", ["あ。"]));

    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(2));
    expect(mockSynth).toHaveBeenCalledTimes(2);
  });

  it("requests again after the limit is reset", async () => {
    mockSynth.mockImplementationOnce(async () => {
      throw new SpeechError(429);
    });
    const { result } = setup();
    act(() => result.current.enqueue("r1", 0, "あ。"));
    await waitFor(() =>
      expect(result.current.error).toBe(SPEECH_LIMIT_MESSAGE),
    );

    act(() => result.current.resetLimit());
    act(() => result.current.enqueue("r2", 0, "いい。"));

    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    expect(result.current.error).toBeNull();
  });

  it("resumes a suspended context before playing", async () => {
    const { result } = setup();
    FakeAudioContext.instances[0].state = "suspended";
    FakeAudioContext.resumable = true;

    act(() => result.current.enqueue("r1", 0, "あ。"));

    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
  });

  it("drops the rest of the queue and reports it when audio cannot resume", async () => {
    FakeAudioContext.initialState = "suspended";
    const { result } = setup();

    act(() => {
      result.current.enqueue("r1", 0, "あ。");
      result.current.enqueue("r1", 1, "いい。");
    });

    await waitFor(() =>
      expect(result.current.error).toBe(SPEECH_INTERRUPTED_MESSAGE),
    );
    expect(FakeAudioContext.sources).toHaveLength(0);
    expect(result.current.activeKey).toBeNull();
  });

  it("waits for the session id instead of dropping the first sentence", async () => {
    const { result, rerender } = setup(null);

    act(() => result.current.enqueue("r1", 0, "あ。"));
    expect(mockSynth).not.toHaveBeenCalled();

    rerender({ sessionId: "s-1" });

    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    expect(mockSynth.mock.calls[0][0]).toBe("s-1");
  });

  it("does nothing before the audio context is unlocked", () => {
    const { result } = renderHook(() =>
      useSpeechPlayback({ sessionId: "s-1" }),
    );

    act(() => result.current.enqueue("r1", 0, "あ。"));

    expect(mockSynth).not.toHaveBeenCalled();
  });

  it("closes the audio context on unmount", () => {
    const { unmount } = setup();

    unmount();

    expect(FakeAudioContext.instances[0].close).toHaveBeenCalled();
  });
});
