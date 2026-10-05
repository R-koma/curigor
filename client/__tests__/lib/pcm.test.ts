import { describe, expect, it } from "vitest";
import {
  Downsampler,
  FrameChunker,
  concatSamples,
  encodeWavBytes,
  frameLevel,
} from "@/lib/pcm";

describe("Downsampler", () => {
  it("keeps the total length across uneven chunks", () => {
    const downsampler = new Downsampler(48000, 16000);
    let total = 0;
    for (let i = 0; i < Math.floor(4800 / 128); i++) {
      total += downsampler.push(new Float32Array(128).fill(0.5)).length;
    }
    total += downsampler.push(new Float32Array(4800 % 128).fill(0.5)).length;
    expect(total).toBe(1600);
  });

  it("averages neighbouring samples", () => {
    const out = new Downsampler(48000, 16000).push(
      Float32Array.from([0, 0.3, 0.6, 0.9, 0.9, 0.9]),
    );
    expect(Array.from(out)).toEqual([
      expect.closeTo(0.3, 5),
      expect.closeTo(0.9, 5),
    ]);
  });

  it("passes samples through when the rates match", () => {
    const out = new Downsampler(16000, 16000).push(
      Float32Array.from([0.1, 0.2]),
    );
    expect(Array.from(out)).toEqual([
      expect.closeTo(0.1, 5),
      expect.closeTo(0.2, 5),
    ]);
  });
});

describe.each([44100, 48000])("Downsampler from %i Hz", (rate) => {
  it("keeps the output length within one sample of the ideal across uneven chunks", () => {
    const downsampler = new Downsampler(rate, 16000);
    const sizes = [128, 100, 333, 7, 480, 1024, 61];
    let input = 0;
    let output = 0;
    for (let i = 0; i < 200; i++) {
      const size = sizes[i % sizes.length];
      input += size;
      output += downsampler.push(new Float32Array(size).fill(0.4)).length;
    }
    expect(Math.abs(output - (input * 16000) / rate)).toBeLessThanOrEqual(1);
  });

  it("keeps a constant level constant", () => {
    const downsampler = new Downsampler(rate, 16000);
    for (let i = 0; i < 20; i++) {
      const out = downsampler.push(new Float32Array(333).fill(0.25));
      for (const value of out) expect(value).toBeCloseTo(0.25, 5);
    }
  });
});

describe("FrameChunker", () => {
  it("emits fixed-size frames and carries the remainder", () => {
    const chunker = new FrameChunker(4);
    expect(chunker.push(new Float32Array(6))).toHaveLength(1);
    const frames = chunker.push(new Float32Array(6));
    expect(frames).toHaveLength(2);
    expect(frames.every((frame) => frame.length === 4)).toBe(true);
  });
});

describe("frameLevel", () => {
  it("returns the RMS", () => {
    expect(frameLevel(Float32Array.from([0.5, -0.5]))).toBeCloseTo(0.5);
    expect(frameLevel(new Float32Array(0))).toBe(0);
  });
});

describe("concatSamples", () => {
  it("joins frames in order", () => {
    const joined = concatSamples([
      Float32Array.from([1]),
      Float32Array.from([2, 3]),
    ]);
    expect(Array.from(joined)).toEqual([1, 2, 3]);
  });
});

describe("encodeWavBytes", () => {
  it("writes a 44-byte PCM16 mono header", () => {
    const bytes = encodeWavBytes(Float32Array.from([0, 1, -1]), 16000);
    const view = new DataView(bytes);
    const ascii = (offset: number) =>
      String.fromCharCode(...new Uint8Array(bytes, offset, 4));
    expect(bytes.byteLength).toBe(44 + 6);
    expect([ascii(0), ascii(8), ascii(12), ascii(36)]).toEqual([
      "RIFF",
      "WAVE",
      "fmt ",
      "data",
    ]);
    expect(view.getUint16(20, true)).toBe(1);
    expect(view.getUint16(22, true)).toBe(1);
    expect(view.getUint32(24, true)).toBe(16000);
    expect(view.getUint16(34, true)).toBe(16);
    expect(view.getUint32(40, true)).toBe(6);
    expect([
      view.getInt16(44, true),
      view.getInt16(46, true),
      view.getInt16(48, true),
    ]).toEqual([0, 32767, -32768]);
  });
});
