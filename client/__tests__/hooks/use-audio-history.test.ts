import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAudioHistory } from "@/hooks/use-audio-history";

class FakeAnalyser {
  fftSize = 0;

  getByteTimeDomainData(target: Uint8Array) {
    target.set(FakeAudioContext.samples.subarray(0, target.length));
  }
}

class FakeAudioContext {
  static samples = new Uint8Array(1024).fill(128);
  static instances: FakeAudioContext[] = [];
  static initialState: AudioContextState = "running";

  state: AudioContextState = FakeAudioContext.initialState;
  closed = false;
  resumed = false;
  source = { connect: vi.fn(), disconnect: vi.fn() };

  constructor() {
    FakeAudioContext.instances.push(this);
  }

  createAnalyser() {
    return new FakeAnalyser();
  }

  createMediaStreamSource() {
    return this.source;
  }

  resume() {
    this.resumed = true;
    return Promise.resolve();
  }

  close() {
    this.closed = true;
    return Promise.resolve();
  }
}

const stream = {} as MediaStream;

beforeEach(() => {
  FakeAudioContext.samples = new Uint8Array(1024).fill(128);
  FakeAudioContext.instances = [];
  FakeAudioContext.initialState = "running";
  vi.stubGlobal("AudioContext", FakeAudioContext);
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useAudioHistory", () => {
  it("starts empty", () => {
    const { result } = renderHook(() => useAudioHistory(stream));

    expect(result.current).toEqual([]);
  });

  it("appends the current level on every tick", () => {
    const { result } = renderHook(() => useAudioHistory(stream));
    FakeAudioContext.samples = new Uint8Array(1024).map((_, i) =>
      i % 2 ? 0 : 255,
    );

    act(() => {
      vi.advanceTimersByTime(50);
    });

    expect(result.current).toEqual([1]);
    expect(FakeAudioContext.instances[0].source.connect).toHaveBeenCalled();
  });

  it("closes the audio context when the stream goes away", () => {
    const { rerender } = renderHook(
      ({ current }: { current: MediaStream | null }) =>
        useAudioHistory(current),
      { initialProps: { current: stream as MediaStream | null } },
    );

    rerender({ current: null });

    const context = FakeAudioContext.instances[0];
    expect(context.closed).toBe(true);
    expect(context.source.disconnect).toHaveBeenCalled();
  });

  it("resumes a suspended audio context", () => {
    FakeAudioContext.initialState = "suspended";

    renderHook(() => useAudioHistory(stream));

    expect(FakeAudioContext.instances[0].resumed).toBe(true);
  });

  it("creates nothing without a stream", () => {
    renderHook(() => useAudioHistory(null));

    expect(FakeAudioContext.instances).toHaveLength(0);
  });

  it("stays empty without the Web Audio API", () => {
    vi.stubGlobal("AudioContext", undefined);

    const { result } = renderHook(() => useAudioHistory(stream));
    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(result.current).toEqual([]);
  });

  it("updates less often when the user prefers reduced motion", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({ matches: true })),
    );
    const { result } = renderHook(() => useAudioHistory(stream));
    FakeAudioContext.samples = new Uint8Array(1024).map((_, i) =>
      i % 2 ? 0 : 255,
    );

    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current).toEqual([]);

    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(result.current).toEqual([1]);
  });

  it("stays empty when the audio context cannot be created", () => {
    vi.stubGlobal(
      "AudioContext",
      class {
        constructor() {
          throw new Error("too many audio contexts");
        }
      },
    );

    const { result } = renderHook(() => useAudioHistory(stream));
    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(result.current).toEqual([]);
  });

  it("tolerates a refused resume", async () => {
    FakeAudioContext.initialState = "suspended";
    const originalResume = FakeAudioContext.prototype.resume;
    FakeAudioContext.prototype.resume = () =>
      Promise.reject(new Error("not allowed"));
    const unhandled = vi.fn();
    process.on("unhandledRejection", unhandled);

    try {
      renderHook(() => useAudioHistory(stream));
      await new Promise((resolve) => setTimeout(resolve, 20));
    } finally {
      process.off("unhandledRejection", unhandled);
      FakeAudioContext.prototype.resume = originalResume;
    }

    expect(unhandled).not.toHaveBeenCalled();
  });

  it("records nothing while the audio context is not running", () => {
    FakeAudioContext.initialState = "suspended";
    FakeAudioContext.samples = new Uint8Array(1024).map((_, i) =>
      i % 2 ? 0 : 255,
    );

    const { result } = renderHook(() => useAudioHistory(stream));
    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(result.current).toEqual([]);
  });
});
