import { CAPTURE_SAMPLE_RATE, concatSamples, encodeWav } from "@/lib/pcm";
import type { LiveTranscriber, TranscriptSegment } from "@/lib/stt/types";

interface SegmentedOptions {
  transcribe: (wav: Blob) => Promise<string>;
  onChange: (segments: TranscriptSegment[]) => void;
  onError: (error: unknown) => void;
}

export function createSegmentedTranscriber({
  transcribe,
  onChange,
  onError,
}: SegmentedOptions): LiveTranscriber {
  let segments: TranscriptSegment[] = [];
  let buffer: Float32Array[] | null = null;
  let nextId = 1;
  let generation = 0;
  let pending: Promise<void>[] = [];

  const update = (id: number, patch: Partial<TranscriptSegment>) => {
    segments = segments.map((segment) =>
      segment.id === id ? { ...segment, ...patch } : segment,
    );
    onChange(segments);
  };

  return {
    method: "segmented",
    begin(preRoll) {
      buffer = [preRoll];
    },
    push(samples) {
      buffer?.push(samples);
    },
    end() {
      if (!buffer) return Promise.resolve();
      const wav = encodeWav(concatSamples(buffer), CAPTURE_SAMPLE_RATE);
      buffer = null;
      const id = nextId++;
      const owner = generation;
      segments = [...segments, { id, text: "", status: "pending" }];
      onChange(segments);
      const job = transcribe(wav).then(
        (text) => {
          if (owner === generation) update(id, { text, status: "done" });
        },
        (error: unknown) => {
          if (owner !== generation) return;
          update(id, { status: "failed" });
          onError(error);
        },
      );
      pending = [...pending, job];
      void job.finally(() => {
        pending = pending.filter((p) => p !== job);
      });
      return job;
    },
    async settled() {
      while (pending.length > 0) await Promise.all(pending);
    },
    segments: () => segments,
    reset() {
      generation += 1;
      buffer = null;
      segments = [];
      onChange(segments);
    },
  };
}
