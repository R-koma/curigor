import { describe, expect, it, vi } from "vitest";
import { FRAME_SAMPLES, type Samples } from "@/lib/pcm";
import {
  SPEECH_CHUNK_SAMPLES,
  SpeechProbabilityStream,
  type SpeechModel,
} from "@/lib/speech-probability";

const frame = (value: number): Samples =>
  new Float32Array(FRAME_SAMPLES).fill(value);

function deferredModel() {
  const calls: {
    chunk: Float32Array;
    resolve: (p: number) => void;
    reject: (e: unknown) => void;
  }[] = [];
  const model: SpeechModel = {
    probability: (chunk) =>
      new Promise<number>((resolve, reject) =>
        calls.push({ chunk, resolve, reject }),
      ),
  };
  return { model, calls };
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("SpeechProbabilityStream", () => {
  it("runs the model on 512-sample chunks and emits each frame once its samples are covered", async () => {
    const { model, calls } = deferredModel();
    const onFrame = vi.fn();
    const stream = new SpeechProbabilityStream(model, onFrame, vi.fn());
    const frames = [1, 2, 3, 4].map(frame);
    for (const f of frames) stream.push(f);

    await flush();
    expect(calls).toHaveLength(1);
    expect(calls[0].chunk).toHaveLength(SPEECH_CHUNK_SAMPLES);
    calls[0].resolve(0.9);
    await flush();
    expect(onFrame.mock.calls).toEqual([[frames[0], 0.9]]);

    expect(calls).toHaveLength(2);
    calls[1].resolve(0.1);
    await flush();
    expect(onFrame.mock.calls).toEqual([
      [frames[0], 0.9],
      [frames[1], 0.1],
      [frames[2], 0.1],
    ]);
  });

  it("keeps frame order while inference is in flight", async () => {
    const { model, calls } = deferredModel();
    const onFrame = vi.fn();
    const stream = new SpeechProbabilityStream(model, onFrame, vi.fn());
    for (let i = 0; i < 16; i++) stream.push(frame(i));
    await flush();
    expect(calls).toHaveLength(1);
    for (let i = 0; i < 10; i++) {
      calls[i].resolve(i / 10);
      await flush();
    }
    const emitted = onFrame.mock.calls.map(([f]) => (f as Samples)[0]);
    expect(emitted).toEqual([...Array(16).keys()]);
  });

  it("drops pending results after close", async () => {
    const { model, calls } = deferredModel();
    const onFrame = vi.fn();
    const stream = new SpeechProbabilityStream(model, onFrame, vi.fn());
    for (let i = 0; i < 4; i++) stream.push(frame(0.1));
    await flush();
    stream.close();
    calls[0].resolve(0.9);
    await flush();
    stream.push(frame(0.1));
    expect(onFrame).not.toHaveBeenCalled();
    expect(calls).toHaveLength(1);
  });

  it("stops and reports when inference fails", async () => {
    const { model, calls } = deferredModel();
    const onFrame = vi.fn();
    const onError = vi.fn();
    const stream = new SpeechProbabilityStream(model, onFrame, onError);
    for (let i = 0; i < 8; i++) stream.push(frame(0.1));
    await flush();
    calls[0].reject(new Error("wasm"));
    await flush();
    expect(onError).toHaveBeenCalledTimes(1);
    expect(calls).toHaveLength(1);
    expect(onFrame).not.toHaveBeenCalled();
  });
});
