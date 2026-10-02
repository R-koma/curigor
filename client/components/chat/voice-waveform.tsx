"use client";

import { useAudioLevels } from "@/hooks/use-audio-levels";

export const WAVEFORM_BAR_COUNT = 40;

const MIN_BAR_PERCENT = 12;

export function VoiceWaveform({ stream }: { stream: MediaStream | null }) {
  const levels = useAudioLevels(stream, WAVEFORM_BAR_COUNT);

  return (
    <div
      role="img"
      aria-label="音声の波形"
      className="flex h-8 flex-1 items-center gap-[2px] overflow-hidden"
    >
      {levels.map((level, i) => (
        <span
          key={i}
          className="w-[3px] shrink-0 rounded-full bg-foreground/70 motion-safe:transition-[height] motion-safe:duration-75"
          style={{
            height: `${Math.max(MIN_BAR_PERCENT, Math.round(level * 100))}%`,
          }}
        />
      ))}
    </div>
  );
}
