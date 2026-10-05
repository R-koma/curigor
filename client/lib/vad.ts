import { FRAME_MS } from "@/lib/pcm";

export interface VadConfig {
  frameMs: number;
  threshold: number;
  startMs: number;
  endMs: number;
  maxSegmentMs: number;
}

export const DEFAULT_VAD_CONFIG: VadConfig = {
  frameMs: FRAME_MS,
  threshold: 0.015,
  startMs: 200,
  endMs: 700,
  maxSegmentMs: 30_000,
};

export const SPEAKING_START_MS = 300;
export const NOISE_CALIBRATION_MS = 500;
const NOISE_MULTIPLIER = 3;

export type VadEvent = "start" | "end" | "split" | null;

export function thresholdFromNoise(
  levels: number[],
  base: number = DEFAULT_VAD_CONFIG.threshold,
): number {
  if (levels.length === 0) return base;
  const mean = levels.reduce((sum, level) => sum + level, 0) / levels.length;
  return Math.max(base, mean * NOISE_MULTIPLIER);
}

export class VoiceActivityDetector {
  private config: VadConfig;
  private speaking = false;
  private aboveMs = 0;
  private belowMs = 0;
  private segmentMs = 0;

  constructor(config: VadConfig = DEFAULT_VAD_CONFIG) {
    this.config = { ...config };
  }

  get inSpeech(): boolean {
    return this.speaking;
  }

  configure(patch: Partial<VadConfig>): void {
    this.config = { ...this.config, ...patch };
  }

  reset(): void {
    this.speaking = false;
    this.aboveMs = 0;
    this.belowMs = 0;
    this.segmentMs = 0;
  }

  push(level: number): VadEvent {
    const { frameMs, threshold, startMs, endMs, maxSegmentMs } = this.config;
    const loud = level >= threshold;
    if (!this.speaking) {
      this.aboveMs = loud ? this.aboveMs + frameMs : 0;
      if (this.aboveMs < startMs) return null;
      this.speaking = true;
      this.segmentMs = this.aboveMs;
      this.belowMs = 0;
      return "start";
    }
    this.segmentMs += frameMs;
    this.belowMs = loud ? 0 : this.belowMs + frameMs;
    if (this.belowMs >= endMs) {
      this.reset();
      return "end";
    }
    if (this.segmentMs >= maxSegmentMs) {
      this.segmentMs = 0;
      return "split";
    }
    return null;
  }
}
