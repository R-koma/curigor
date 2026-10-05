export type SttMethod = "segmented" | "streaming";

export interface TranscriptSegment {
  id: number;
  text: string;
  status: "pending" | "done" | "failed";
}

export interface LiveTranscriber {
  readonly method: SttMethod;
  begin(preRoll: Float32Array): void;
  push(samples: Float32Array): void;
  end(): Promise<void>;
  settled(): Promise<void>;
  segments(): TranscriptSegment[];
  reset(): void;
}
