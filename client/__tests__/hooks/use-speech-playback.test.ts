import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  MAX_CACHED_RESPONSES,
  SPEECH_FAILED_MESSAGE,
  SPEECH_INTERRUPTED_MESSAGE,
  SPEECH_LIMIT_MESSAGE,
  useSpeechPlayback,
} from "@/hooks/use-speech-playback";
import { SpeechError, streamSpeech } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, streamSpeech: vi.fn() };
});

const mockStream = vi.mocked(streamSpeech);

class FakeSource {
  buffer: { length: number; duration: number } | null = null;
  onended: (() => void) | null = null;
  startedAt: number | null = null;
  connect = vi.fn();
  start = vi.fn((at: number) => {
    this.startedAt = at;
  });
  stop = vi.fn(() => this.onended?.());
}

class FakeAudioContext {
  static sources: FakeSource[] = [];
  static instances: FakeAudioContext[] = [];
  static initialState: AudioContextState = "running";
  state: AudioContextState = FakeAudioContext.initialState;
  currentTime = 0;
  destination = {};
  constructor() {
    FakeAudioContext.instances.push(this);
  }
  resume = vi.fn(async () => {});
  close = vi.fn(async () => {});
  createBuffer = vi.fn((_channels: number, length: number, rate: number) => ({
    length,
    duration: length / rate,
    copyToChannel: vi.fn(),
  }));
  createBufferSource = vi.fn(() => {
    const source = new FakeSource();
    FakeAudioContext.sources.push(source);
    return source as unknown as AudioBufferSourceNode;
  });
}

function pcm(samples: number): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      controller.enqueue(new Uint8Array(samples * 2));
      controller.close();
    },
  });
}

const endAll = () =>
  act(() => FakeAudioContext.sources.forEach((source) => source.onended?.()));

beforeEach(() => {
  FakeAudioContext.sources = [];
  FakeAudioContext.instances = [];
  FakeAudioContext.initialState = "running";
  mockStream.mockReset();
  mockStream.mockImplementation(async (_id, text) => pcm(text.length * 2400));
  vi.stubGlobal("AudioContext", FakeAudioContext);
});

afterEach(() => vi.unstubAllGlobals());

function setup(
  options: {
    sessionId?: string | null;
    speed?: number;
    onPlaybackStart?: (key: string, index: number) => void;
  } = {},
) {
  const hook = renderHook(
    (props: { speed: number; sessionId: string | null }) =>
      useSpeechPlayback({
        sessionId: props.sessionId,
        speed: props.speed,
        onPlaybackStart: options.onPlaybackStart,
      }),
    {
      initialProps: {
        speed: options.speed ?? 1,
        sessionId: options.sessionId === undefined ? "s-1" : options.sessionId,
      },
    },
  );
  act(() => hook.result.current.unlock());
  return hook;
}

describe("useSpeechPlayback", () => {
  it("schedules sentences back to back without gaps", async () => {
    const { result } = setup();
    act(() => {
      result.current.enqueue("r1", 0, "あ。");
      result.current.enqueue("r1", 1, "いい。");
    });

    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(2));
    const [first, second] = FakeAudioContext.sources;
    expect(first.startedAt).toBeCloseTo(0.05);
    expect(second.startedAt).toBeCloseTo(0.05 + 0.2);
    expect(result.current.activeKey).toBe("r1");

    endAll();
    await waitFor(() => expect(result.current.activeKey).toBeNull());
  });

  it("prefetches at most two sentences", async () => {
    mockStream.mockImplementation(() => new Promise(() => {}));
    const { result } = setup();
    act(() => {
      result.current.enqueue("r1", 0, "あ。");
      result.current.enqueue("r1", 1, "い。");
      result.current.enqueue("r1", 2, "う。");
    });
    await waitFor(() => expect(mockStream).toHaveBeenCalledTimes(2));
  });

  it("passes the speed and notifies the start of each sentence", async () => {
    const onPlaybackStart = vi.fn();
    const { result } = setup({ speed: 1.25, onPlaybackStart });
    act(() => result.current.enqueue("r1", 0, "あ。"));

    await waitFor(() => expect(onPlaybackStart).toHaveBeenCalledWith("r1", 0));
    expect(mockStream.mock.calls[0][2]).toBe(1.25);
  });

  it("replays from the cache without refetching", async () => {
    const { result } = setup();
    act(() => result.current.playAll("r1", ["あ。"]));
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    endAll();

    act(() => result.current.playAll("r1", ["あ。"]));
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(2));
    expect(mockStream).toHaveBeenCalledTimes(1);
  });

  it("refetches after the speed changes", async () => {
    const { result, rerender } = setup();
    act(() => result.current.playAll("r1", ["あ。"]));
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    endAll();

    rerender({ speed: 1.5, sessionId: "s-1" });
    act(() => result.current.playAll("r1", ["あ。"]));
    await waitFor(() => expect(mockStream).toHaveBeenCalledTimes(2));
    expect(mockStream.mock.calls[1][2]).toBe(1.5);
  });

  it("stop silences every scheduled chunk", async () => {
    const { result } = setup();
    act(() => {
      result.current.enqueue("r1", 0, "あ。");
      result.current.enqueue("r1", 1, "い。");
    });
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(2));

    act(() => result.current.stop());

    expect(
      FakeAudioContext.sources.every((s) => s.stop.mock.calls.length === 1),
    ).toBe(true);
    expect(result.current.activeKey).toBeNull();
  });

  it("stops queueing after the daily limit", async () => {
    mockStream.mockRejectedValue(new SpeechError(429));
    const { result } = setup();
    act(() => result.current.enqueue("r1", 0, "あ。"));
    await waitFor(() =>
      expect(result.current.error).toBe(SPEECH_LIMIT_MESSAGE),
    );

    act(() => result.current.enqueue("r2", 0, "い。"));
    expect(mockStream).toHaveBeenCalledTimes(1);
  });

  it("shows a failure for other errors", async () => {
    mockStream.mockRejectedValue(new SpeechError(502));
    const { result } = setup();
    act(() => result.current.enqueue("r1", 0, "あ。"));
    await waitFor(() =>
      expect(result.current.error).toBe(SPEECH_FAILED_MESSAGE),
    );
  });

  it("gives up when the context cannot resume", async () => {
    FakeAudioContext.initialState = "suspended";
    const { result } = setup();
    act(() => result.current.enqueue("r1", 0, "あ。"));
    await waitFor(() =>
      expect(result.current.error).toBe(SPEECH_INTERRUPTED_MESSAGE),
    );
  });

  it("does nothing before unlock", () => {
    const hook = renderHook(() => useSpeechPlayback({ sessionId: "s-1" }));
    act(() => hook.result.current.enqueue("r1", 0, "あ。"));
    expect(mockStream).not.toHaveBeenCalled();
  });

  it("stop aborts in-flight requests", async () => {
    mockStream.mockImplementation(() => new Promise(() => {}));
    const { result } = setup();
    act(() => result.current.enqueue("r1", 0, "あ。"));
    await waitFor(() => expect(mockStream).toHaveBeenCalledTimes(1));
    const signal = mockStream.mock.calls[0][3] as AbortSignal;

    act(() => result.current.stop());

    expect(signal.aborted).toBe(true);
    expect(result.current.activeKey).toBeNull();
  });

  it("forgets the oldest response beyond the keeping limit", async () => {
    const { result } = setup();
    for (let k = 0; k <= MAX_CACHED_RESPONSES; k++) {
      act(() => result.current.enqueue(`r${k}`, 0, "あ。"));
    }
    await waitFor(() =>
      expect(FakeAudioContext.sources).toHaveLength(MAX_CACHED_RESPONSES + 1),
    );
    const calls = mockStream.mock.calls.length;

    act(() => result.current.playAll(`r${MAX_CACHED_RESPONSES}`, ["あ。"]));
    await waitFor(() =>
      expect(FakeAudioContext.sources).toHaveLength(MAX_CACHED_RESPONSES + 2),
    );
    expect(mockStream.mock.calls.length).toBe(calls);

    act(() => result.current.playAll("r0", ["あ。"]));
    await waitFor(() =>
      expect(FakeAudioContext.sources).toHaveLength(MAX_CACHED_RESPONSES + 3),
    );
    expect(mockStream.mock.calls.length).toBe(calls + 1);
  });

  it("waits for the session id instead of dropping the first sentence", async () => {
    const { result, rerender } = setup({ sessionId: null });

    act(() => result.current.enqueue("r1", 0, "あ。"));
    expect(mockStream).not.toHaveBeenCalled();

    rerender({ speed: 1, sessionId: "s-1" });

    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    expect(mockStream.mock.calls[0][0]).toBe("s-1");
  });

  it("closes the audio context on unmount", () => {
    const { unmount } = setup();

    unmount();

    expect(FakeAudioContext.instances[0].close).toHaveBeenCalled();
  });

  it("hold stops the audio and release replays from the audible sentence without refetching", async () => {
    const { result } = setup();
    act(() => {
      result.current.enqueue("r1", 0, "あ。");
      result.current.enqueue("r1", 1, "い。");
    });
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(2));
    act(() => FakeAudioContext.sources[0].onended?.());

    act(() => result.current.hold());
    expect(FakeAudioContext.sources[1].stop).toHaveBeenCalled();
    expect(result.current.activeKey).toBeNull();

    act(() => result.current.release());
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(3));
    expect(FakeAudioContext.sources[2].startedAt).toBeCloseTo(0.05);
    expect(result.current.activeKey).toBe("r1");
    expect(mockStream).toHaveBeenCalledTimes(2);
  });

  it("keeps sentences enqueued while held and plays them on release", async () => {
    const { result } = setup();
    act(() => result.current.hold());
    act(() => result.current.enqueue("r1", 0, "あ。"));
    expect(mockStream).not.toHaveBeenCalled();
    expect(FakeAudioContext.sources).toHaveLength(0);

    act(() => result.current.release());
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
  });

  it("keeps a sentence that is still downloading when held", async () => {
    let finish: (stream: ReadableStream<Uint8Array>) => void = () => {};
    mockStream.mockImplementationOnce(
      () => new Promise((resolve) => (finish = resolve)),
    );
    const { result } = setup();
    act(() => result.current.enqueue("r1", 0, "あ。"));
    await waitFor(() => expect(mockStream).toHaveBeenCalledTimes(1));

    act(() => result.current.hold());
    await act(async () => finish(pcm(4800)));
    expect(FakeAudioContext.sources).toHaveLength(0);

    act(() => result.current.release());
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    expect(mockStream).toHaveBeenCalledTimes(1);
  });

  it("refetches a held sentence whose audio was dropped", async () => {
    const { result, rerender } = setup();
    act(() => result.current.enqueue("r1", 0, "あ。"));
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));

    act(() => result.current.hold());
    rerender({ speed: 1.5, sessionId: "s-1" });
    act(() => result.current.release());
    await waitFor(() => expect(mockStream).toHaveBeenCalledTimes(2));
    expect(mockStream.mock.calls[1][2]).toBe(1.5);
  });

  it("discardHeld drops the held sentences", async () => {
    const { result } = setup();
    act(() => {
      result.current.hold();
      result.current.enqueue("r1", 0, "あ。");
      result.current.discardHeld();
      result.current.release();
    });
    expect(mockStream).not.toHaveBeenCalled();

    act(() => result.current.enqueue("r2", 0, "い。"));
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
  });

  it("stop ends the hold", async () => {
    const { result } = setup();
    act(() => {
      result.current.hold();
      result.current.stop();
      result.current.enqueue("r1", 0, "あ。");
    });
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
  });
});
