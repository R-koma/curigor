import { afterEach, describe, expect, it, vi } from "vitest";
import { FRAME_SAMPLES } from "@/lib/pcm";
import { MicUnsupportedError, openMicCapture } from "@/lib/mic-capture";

class FakeNode {
  port = {
    onmessage: null as ((event: MessageEvent<Float32Array>) => void) | null,
  };
  connect = vi.fn((target: unknown) => target);
  disconnect = vi.fn();
}

function installAudio() {
  const track = { stop: vi.fn() };
  const stream = { getTracks: () => [track] };
  const getUserMedia = vi.fn(async () => stream);
  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });
  const node = new FakeNode();
  const context = {
    sampleRate: 48000,
    state: "running" as AudioContextState,
    resume: vi.fn(async () => {}),
    destination: {},
    audioWorklet: { addModule: vi.fn(async () => {}) },
    createMediaStreamSource: vi.fn(() => new FakeNode()),
    createGain: vi.fn(() => ({
      gain: { value: 1 },
      connect: vi.fn(() => ({})),
    })),
    close: vi.fn(async () => {}),
  };
  vi.stubGlobal(
    "AudioContext",
    vi.fn(function () {
      return context;
    }),
  );
  vi.stubGlobal(
    "AudioWorkletNode",
    vi.fn(function () {
      return node;
    }),
  );
  return { getUserMedia, node, context, track };
}

afterEach(() => vi.unstubAllGlobals());

describe("openMicCapture", () => {
  it("opens the mic with echo cancellation and emits 20ms frames at 16kHz", async () => {
    const { getUserMedia, node } = installAudio();
    const frames: Float32Array[] = [];

    await openMicCapture((frame) => frames.push(frame));
    node.port.onmessage?.({
      data: new Float32Array(960),
    } as MessageEvent<Float32Array>);

    expect(getUserMedia).toHaveBeenCalledWith({
      audio: expect.objectContaining({
        echoCancellation: true,
        noiseSuppression: true,
      }),
    });
    expect(frames).toHaveLength(1);
    expect(frames[0]).toHaveLength(FRAME_SAMPLES);
  });

  it("close stops the tracks and the context", async () => {
    const { track, context, node } = installAudio();
    const capture = await openMicCapture(() => {});
    capture.close();
    expect(track.stop).toHaveBeenCalled();
    expect(context.close).toHaveBeenCalled();
    expect(node.port.onmessage).toBeNull();
  });

  it("proceeds when a suspended context never resumes", async () => {
    vi.useFakeTimers();
    try {
      const { context } = installAudio();
      context.state = "suspended";
      context.resume = vi.fn(() => new Promise<void>(() => {}));
      const opened = openMicCapture(() => {});
      await vi.advanceTimersByTimeAsync(1000);
      await expect(opened).resolves.toHaveProperty("close");
    } finally {
      vi.useRealTimers();
    }
  });

  it("throws MicUnsupportedError without AudioWorklet", async () => {
    installAudio();
    vi.stubGlobal("AudioWorkletNode", undefined);
    await expect(openMicCapture(() => {})).rejects.toBeInstanceOf(
      MicUnsupportedError,
    );
  });

  it("releases the mic when the worklet fails to load", async () => {
    const { context, track } = installAudio();
    context.audioWorklet.addModule.mockRejectedValue(new Error("load"));
    await expect(openMicCapture(() => {})).rejects.toThrow("load");
    expect(track.stop).toHaveBeenCalled();
  });
  it("releases the mic when the AudioContext cannot be created", async () => {
    const { track } = installAudio();
    vi.stubGlobal(
      "AudioContext",
      vi.fn(function () {
        throw new Error("context");
      }),
    );
    await expect(openMicCapture(() => {})).rejects.toThrow("context");
    expect(track.stop).toHaveBeenCalled();
  });

  it("releases the mic and the context when the worklet node cannot be created", async () => {
    const { context, track } = installAudio();
    vi.stubGlobal(
      "AudioWorkletNode",
      vi.fn(function () {
        throw new Error("node");
      }),
    );
    await expect(openMicCapture(() => {})).rejects.toThrow("node");
    expect(track.stop).toHaveBeenCalled();
    expect(context.close).toHaveBeenCalled();
  });

  it("resumes a suspended context before reporting the mic open", async () => {
    const { context } = installAudio();
    context.state = "suspended";
    await openMicCapture(() => {});
    expect(context.resume).toHaveBeenCalled();
  });

  it("releases the mic when resuming the context fails", async () => {
    const { context, track } = installAudio();
    context.state = "suspended";
    context.resume.mockRejectedValue(new Error("resume"));
    await expect(openMicCapture(() => {})).rejects.toThrow("resume");
    expect(track.stop).toHaveBeenCalled();
    expect(context.close).toHaveBeenCalled();
  });
});
