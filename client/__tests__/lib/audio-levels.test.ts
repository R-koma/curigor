import { describe, expect, it } from "vitest";
import { pushLevel, rmsLevel, visibleLevels } from "@/lib/audio-levels";

describe("rmsLevel", () => {
  it("is zero for silence", () => {
    expect(rmsLevel(new Uint8Array(256).fill(128))).toBe(0);
  });

  it("is one for a full-scale signal", () => {
    const samples = new Uint8Array(256).map((_, i) => (i % 2 ? 0 : 255));
    expect(rmsLevel(samples)).toBe(1);
  });

  it("scales a quiet voice up so it still shows", () => {
    const samples = new Uint8Array(256).map((_, i) => (i % 2 ? 118 : 138));
    const level = rmsLevel(samples);
    expect(level).toBeGreaterThan(0.2);
    expect(level).toBeLessThan(0.3);
  });

  it("is zero for no samples", () => {
    expect(rmsLevel(new Uint8Array(0))).toBe(0);
  });
});

describe("pushLevel", () => {
  it("appends the newest level", () => {
    expect(pushLevel([0.1, 0.2], 0.9, 5)).toEqual([0.1, 0.2, 0.9]);
  });

  it("drops the oldest levels beyond the limit", () => {
    expect(pushLevel([0.1, 0.2, 0.3], 0.9, 3)).toEqual([0.2, 0.3, 0.9]);
  });
});

describe("visibleLevels", () => {
  it("pads with silence on the left when the history is short", () => {
    expect(visibleLevels([0.5, 1], 4)).toEqual([0, 0, 0.5, 1]);
  });

  it("keeps only the newest levels when the history is long", () => {
    expect(visibleLevels([0.1, 0.2, 0.3, 0.4], 2)).toEqual([0.3, 0.4]);
  });

  it("is flat for an empty history", () => {
    expect(visibleLevels([], 3)).toEqual([0, 0, 0]);
  });
});
