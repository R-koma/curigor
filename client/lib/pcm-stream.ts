import type { Samples } from "@/lib/pcm";

export class SentenceAudio {
  readonly chunks: Samples[] = [];
  readonly done: Promise<boolean>;
  private settle!: (ok: boolean) => void;
  private readonly listeners = new Set<(chunk: Samples) => void>();

  constructor() {
    this.done = new Promise((resolve) => {
      this.settle = resolve;
    });
  }

  push(chunk: Samples): void {
    this.chunks.push(chunk);
    this.listeners.forEach((listener) => listener(chunk));
  }

  finish(ok: boolean): void {
    this.listeners.clear();
    this.settle(ok);
  }

  subscribe(listener: (chunk: Samples) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }
}

export async function readPcm16(
  body: ReadableStream<Uint8Array>,
  onChunk: (samples: Samples) => void,
): Promise<void> {
  const reader = body.getReader();
  let carry: number | null = null;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) return;
    let bytes = value;
    if (carry !== null) {
      const merged = new Uint8Array(bytes.length + 1);
      merged[0] = carry;
      merged.set(bytes, 1);
      bytes = merged;
      carry = null;
    }
    if (bytes.length % 2 === 1) {
      carry = bytes[bytes.length - 1];
      bytes = bytes.subarray(0, bytes.length - 1);
    }
    if (bytes.length === 0) continue;
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const samples = new Float32Array(bytes.length / 2);
    for (let i = 0; i < samples.length; i++) {
      samples[i] = view.getInt16(i * 2, true) / 32768;
    }
    onChunk(samples);
  }
}
