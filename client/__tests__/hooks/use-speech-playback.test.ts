import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSpeechPlayback } from "@/hooks/use-speech-playback";
import { SpeechError, synthesizeSpeech } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, synthesizeSpeech: vi.fn() };
});

const mockSynth = vi.mocked(synthesizeSpeech);

class FakeSource {
  buffer: { id: number } | null = null;
  onended: (() => void) | null = null;
  connect = vi.fn();
  start = vi.fn();
  stop = vi.fn(() => this.onended?.());
}

class FakeAudioContext {
  static sources: FakeSource[] = [];
  state = "running";
  destination = {};
  resume = vi.fn();
  decodeAudioData = vi.fn(async (data: ArrayBuffer) => ({
    id: new Uint8Array(data)[0],
  }));
  createBufferSource = vi.fn(() => {
    const source = new FakeSource();
    FakeAudioContext.sources.push(source);
    return source as unknown as AudioBufferSourceNode;
  });
}

const ok = async (_id: string, text: string) =>
  new Uint8Array([text.length]).buffer;

beforeEach(() => {
  FakeAudioContext.sources = [];
  mockSynth.mockReset();
  mockSynth.mockImplementation(ok);
  vi.stubGlobal("AudioContext", FakeAudioContext);
});

afterEach(() => vi.unstubAllGlobals());

function setup() {
  const hook = renderHook(() => useSpeechPlayback({ sessionId: "s-1" }));
  act(() => hook.result.current.unlock());
  return hook;
}

describe("useSpeechPlayback", () => {
  it("plays sentences in order and prefetches only the next one", async () => {
    const { result } = setup();

    act(() => {
      result.current.enqueue("あ。");
      result.current.enqueue("いい。");
      result.current.enqueue("ううう。");
    });

    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    expect(mockSynth).toHaveBeenCalledTimes(2);
    expect(result.current.isSpeaking).toBe(true);

    act(() => FakeAudioContext.sources[0].onended?.());
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(2));
    await waitFor(() => expect(mockSynth).toHaveBeenCalledTimes(3));

    act(() => FakeAudioContext.sources[1].onended?.());
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(3));
    act(() => FakeAudioContext.sources[2].onended?.());

    expect(FakeAudioContext.sources.map((s) => s.buffer?.id)).toEqual([
      2, 3, 4,
    ]);
    await waitFor(() => expect(result.current.isSpeaking).toBe(false));
  });

  it("stops the sound, aborts pending requests and drops the queue", async () => {
    const { result } = setup();
    act(() => {
      result.current.enqueue("あ。");
      result.current.enqueue("いい。");
    });
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    const signal = mockSynth.mock.calls[0][2] as AbortSignal;

    act(() => result.current.stop());

    expect(FakeAudioContext.sources[0].stop).toHaveBeenCalled();
    expect(signal.aborted).toBe(true);
    expect(result.current.isSpeaking).toBe(false);
    await act(async () => {
      await Promise.resolve();
    });
    expect(FakeAudioContext.sources).toHaveLength(1);
  });

  it("plays again after a stop", async () => {
    const { result } = setup();
    act(() => result.current.enqueue("あ。"));
    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    act(() => result.current.stop());

    act(() => result.current.enqueue("いい。"));

    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(2));
    expect(FakeAudioContext.sources[1].buffer?.id).toBe(3);
  });

  it("skips a sentence that fails and reports it", async () => {
    mockSynth.mockImplementationOnce(async () => {
      throw new Error("boom");
    });
    const { result } = setup();

    act(() => {
      result.current.enqueue("あ。");
      result.current.enqueue("いい。");
    });

    await waitFor(() => expect(FakeAudioContext.sources).toHaveLength(1));
    expect(FakeAudioContext.sources[0].buffer?.id).toBe(3);
    expect(result.current.error).toBe("読み上げに失敗しました");
  });

  it("stops requesting after the daily limit", async () => {
    mockSynth.mockImplementationOnce(async () => {
      throw new SpeechError(429);
    });
    const { result } = setup();

    act(() => {
      result.current.enqueue("あ。");
      result.current.enqueue("いい。");
    });
    await waitFor(() =>
      expect(result.current.error).toBe("今日の読み上げの上限に達しました"),
    );
    const calls = mockSynth.mock.calls.length;

    act(() => result.current.enqueue("ううう。"));

    expect(mockSynth.mock.calls.length).toBe(calls);
    expect(FakeAudioContext.sources).toHaveLength(0);
  });

  it("does nothing before the audio context is unlocked", () => {
    const { result } = renderHook(() =>
      useSpeechPlayback({ sessionId: "s-1" }),
    );

    act(() => result.current.enqueue("あ。"));

    expect(mockSynth).not.toHaveBeenCalled();
  });
});
