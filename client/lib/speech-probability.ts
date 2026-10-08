import type { InferenceSession, Tensor } from "onnxruntime-web/wasm";
import { CAPTURE_SAMPLE_RATE, concatSamples, type Samples } from "@/lib/pcm";

export const SPEECH_CHUNK_SAMPLES = 512;
// Silero v5 以降は直前のチャンクの末尾 64 サンプルを先頭に付けて渡す（公式実装の OnnxWrapper と同じ）
const CONTEXT_SAMPLES = 64;
const STATE_SIZE = 2 * 128;
const MODEL_URL = "/models/silero_vad_16k_op15.onnx";

export interface SpeechModel {
  probability(chunk: Float32Array): Promise<number>;
}

export type LoadSpeechModel = () => Promise<SpeechModel>;

type Ort = typeof import("onnxruntime-web/wasm");

let runtime: Promise<{ ort: Ort; session: InferenceSession }> | null = null;

function loadRuntime() {
  runtime ??= (async () => {
    const ort = await import("onnxruntime-web/wasm");
    ort.env.wasm.numThreads = 1;
    const session = await ort.InferenceSession.create(MODEL_URL);
    return { ort, session };
  })().catch((error: unknown) => {
    runtime = null;
    throw error;
  });
  return runtime;
}

export const loadSileroModel: LoadSpeechModel = async () => {
  const { ort, session } = await loadRuntime();
  const sr = new ort.Tensor(
    "int64",
    BigInt64Array.from([BigInt(CAPTURE_SAMPLE_RATE)]),
    [],
  );
  let state: Tensor = new ort.Tensor(
    "float32",
    new Float32Array(STATE_SIZE),
    [2, 1, 128],
  );
  let context = new Float32Array(CONTEXT_SAMPLES);
  return {
    async probability(chunk) {
      const input = new Float32Array(CONTEXT_SAMPLES + chunk.length);
      input.set(context);
      input.set(chunk, CONTEXT_SAMPLES);
      context = chunk.slice(-CONTEXT_SAMPLES);
      const out = await session.run({
        input: new ort.Tensor("float32", input, [1, input.length]),
        state,
        sr,
      });
      state = out.stateN;
      return (out.output.data as Float32Array)[0];
    },
  };
};

interface PendingFrame {
  frame: Samples;
  end: number;
}

export class SpeechProbabilityStream {
  private buffer: Samples = new Float32Array(0);
  private pending: PendingFrame[] = [];
  private received = 0;
  private chunked = 0;
  private queue: Promise<void> = Promise.resolve();
  private closed = false;

  constructor(
    private readonly model: SpeechModel,
    private readonly onFrame: (frame: Samples, probability: number) => void,
    private readonly onError: (error: unknown) => void,
  ) {}

  push(frame: Samples): void {
    if (this.closed) return;
    this.received += frame.length;
    this.pending.push({ frame, end: this.received });
    this.buffer = concatSamples([this.buffer, frame]);
    while (this.buffer.length >= SPEECH_CHUNK_SAMPLES) {
      const chunk = this.buffer.slice(0, SPEECH_CHUNK_SAMPLES);
      this.buffer = this.buffer.slice(SPEECH_CHUNK_SAMPLES);
      this.chunked += SPEECH_CHUNK_SAMPLES;
      const covered = this.pending.findIndex(({ end }) => end > this.chunked);
      const ready = this.pending.splice(
        0,
        covered === -1 ? this.pending.length : covered,
      );
      this.queue = this.queue.then(() => this.infer(chunk, ready));
    }
  }

  close(): void {
    this.closed = true;
    this.pending = [];
    this.buffer = new Float32Array(0);
  }

  private async infer(chunk: Float32Array, ready: PendingFrame[]) {
    if (this.closed) return;
    let probability: number;
    try {
      probability = await this.model.probability(chunk);
    } catch (error) {
      if (this.closed) return;
      this.close();
      this.onError(error);
      return;
    }
    if (this.closed) return;
    for (const { frame } of ready) this.onFrame(frame, probability);
  }
}
