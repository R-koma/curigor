export type Samples = Float32Array<ArrayBuffer>;

export const CAPTURE_SAMPLE_RATE = 16000;
export const FRAME_MS = 20;
export const FRAME_SAMPLES = (CAPTURE_SAMPLE_RATE * FRAME_MS) / 1000;

export function concatSamples(parts: Float32Array[]): Samples {
  const out = new Float32Array(
    parts.reduce((sum, part) => sum + part.length, 0),
  );
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

export class Downsampler {
  private readonly ratio: number;
  private position = 0;
  private carry: Float32Array = new Float32Array(0);

  constructor(fromRate: number, toRate: number) {
    this.ratio = fromRate / toRate;
  }

  push(input: Float32Array): Samples {
    const data = concatSamples([this.carry, input]);
    const out: number[] = [];
    let position = this.position;
    while (position + this.ratio <= data.length) {
      const start = Math.floor(position);
      const end = Math.max(start + 1, Math.floor(position + this.ratio));
      let sum = 0;
      for (let i = start; i < end; i++) sum += data[i];
      out.push(sum / (end - start));
      position += this.ratio;
    }
    const consumed = Math.floor(position);
    this.carry = data.slice(consumed);
    this.position = position - consumed;
    return Float32Array.from(out);
  }
}

export class FrameChunker {
  private pending: Float32Array = new Float32Array(0);

  constructor(private readonly frameSize: number) {}

  push(samples: Float32Array): Samples[] {
    const data = concatSamples([this.pending, samples]);
    const frames: Samples[] = [];
    let offset = 0;
    while (offset + this.frameSize <= data.length) {
      frames.push(data.slice(offset, offset + this.frameSize));
      offset += this.frameSize;
    }
    this.pending = data.slice(offset);
    return frames;
  }
}

export function frameLevel(samples: Float32Array): number {
  if (samples.length === 0) return 0;
  let sum = 0;
  for (const sample of samples) sum += sample * sample;
  return Math.sqrt(sum / samples.length);
}

export function encodeWavBytes(
  samples: Float32Array,
  sampleRate: number,
): ArrayBuffer {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const ascii = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++)
      view.setUint8(offset + i, text.charCodeAt(i));
  };
  ascii(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  ascii(8, "WAVE");
  ascii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  ascii(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, i) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(
      44 + i * 2,
      clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff,
      true,
    );
  });
  return buffer;
}

export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  return new Blob([encodeWavBytes(samples, sampleRate)], { type: "audio/wav" });
}
