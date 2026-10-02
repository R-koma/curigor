export const LEVEL_INTERVAL_MS = 50;
export const REDUCED_MOTION_LEVEL_INTERVAL_MS = 250;

const LEVEL_GAIN = 3;

export function rmsLevel(samples: Uint8Array): number {
  if (samples.length === 0) return 0;
  let sum = 0;
  for (const sample of samples) {
    const centered = (sample - 128) / 128;
    sum += centered * centered;
  }
  return Math.min(1, Math.sqrt(sum / samples.length) * LEVEL_GAIN);
}

export const MAX_LEVEL_HISTORY = 600;

export function pushLevel(
  levels: number[],
  level: number,
  limit: number = MAX_LEVEL_HISTORY,
): number[] {
  return [...levels, level].slice(-limit);
}

export function visibleLevels(history: number[], count: number): number[] {
  const recent = history.slice(-count);
  return [...Array.from({ length: count - recent.length }, () => 0), ...recent];
}
