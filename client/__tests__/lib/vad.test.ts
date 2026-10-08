import { describe, expect, it } from "vitest";
import {
  DEFAULT_VAD_CONFIG,
  SPEAKING_START_MS,
  VOLUME_THRESHOLD,
  VoiceActivityDetector,
  thresholdFromNoise,
  type VadEvent,
} from "@/lib/vad";

const LOUD = 0.9;
const FADING = 0.4;
const QUIET = 0;
const frames = (ms: number) => ms / DEFAULT_VAD_CONFIG.frameMs;

function feed(
  vad: VoiceActivityDetector,
  level: number,
  ms: number,
): VadEvent[] {
  const events: VadEvent[] = [];
  for (let i = 0; i < frames(ms); i++) {
    const event = vad.push(level);
    if (event) events.push(event);
  }
  return events;
}

describe("VoiceActivityDetector", () => {
  it("starts after 200ms above the threshold", () => {
    const vad = new VoiceActivityDetector();
    expect(feed(vad, LOUD, 180)).toEqual([]);
    expect(feed(vad, LOUD, 20)).toEqual(["start"]);
    expect(vad.inSpeech).toBe(true);
  });

  it("ignores a short burst", () => {
    const vad = new VoiceActivityDetector();
    feed(vad, LOUD, 100);
    feed(vad, QUIET, 20);
    expect(feed(vad, LOUD, 180)).toEqual([]);
  });

  it("ends after 700ms below the threshold", () => {
    const vad = new VoiceActivityDetector();
    feed(vad, LOUD, 400);
    expect(feed(vad, QUIET, 680)).toEqual([]);
    expect(feed(vad, QUIET, 20)).toEqual(["end"]);
    expect(vad.inSpeech).toBe(false);
  });

  it("does not start between the end and start thresholds", () => {
    const vad = new VoiceActivityDetector();
    expect(feed(vad, FADING, 1000)).toEqual([]);
  });

  it("stays in speech between the end and start thresholds", () => {
    const vad = new VoiceActivityDetector();
    feed(vad, LOUD, 400);
    expect(feed(vad, FADING, 1000)).toEqual([]);
    expect(vad.inSpeech).toBe(true);
  });

  it("keeps the segment open through short pauses", () => {
    const vad = new VoiceActivityDetector();
    feed(vad, LOUD, 400);
    feed(vad, QUIET, 600);
    expect(feed(vad, LOUD, 100)).toEqual([]);
    expect(feed(vad, QUIET, 680)).toEqual([]);
  });

  it("splits a segment longer than 30 seconds and stays in speech", () => {
    const vad = new VoiceActivityDetector();
    const events = feed(vad, LOUD, 30_000 + 400);
    expect(events).toEqual(["start", "split"]);
    expect(vad.inSpeech).toBe(true);
  });

  it("starts later while the assistant is speaking", () => {
    const vad = new VoiceActivityDetector();
    vad.configure({ startMs: SPEAKING_START_MS });
    expect(feed(vad, LOUD, 280)).toEqual([]);
    expect(feed(vad, LOUD, 20)).toEqual(["start"]);
  });

  it("reset leaves speech without emitting", () => {
    const vad = new VoiceActivityDetector();
    feed(vad, LOUD, 400);
    vad.reset();
    expect(vad.inSpeech).toBe(false);
    expect(feed(vad, QUIET, 700)).toEqual([]);
  });
});

describe("thresholdFromNoise", () => {
  it("never drops below the base", () => {
    expect(thresholdFromNoise([0, 0.001])).toBe(VOLUME_THRESHOLD);
  });

  it("rises above a noisy room", () => {
    expect(thresholdFromNoise([0.02, 0.02])).toBeCloseTo(0.06);
  });
});
