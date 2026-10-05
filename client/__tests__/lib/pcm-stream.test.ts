import { describe, expect, it, vi } from "vitest";
import { SentenceAudio, readPcm16 } from "@/lib/pcm-stream";

function streamOf(...chunks: number[][]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(Uint8Array.from(chunk)));
      controller.close();
    },
  });
}

describe("readPcm16", () => {
  it("decodes little-endian int16 across odd chunk boundaries", async () => {
    const out: number[] = [];
    await readPcm16(streamOf([0x00, 0x40, 0x00], [0xc0]), (samples) =>
      out.push(...samples),
    );
    expect(out).toEqual([0.5, -0.5]);
  });
});

describe("SentenceAudio", () => {
  it("keeps chunks, notifies subscribers and resolves done", async () => {
    const audio = new SentenceAudio();
    const listener = vi.fn();
    const unsubscribe = audio.subscribe(listener);
    audio.push(Float32Array.from([0.1]));
    unsubscribe();
    audio.push(Float32Array.from([0.2]));
    audio.finish(true);

    expect(listener).toHaveBeenCalledTimes(1);
    expect(audio.chunks).toHaveLength(2);
    await expect(audio.done).resolves.toBe(true);
  });
});
