"use client";

import { useEffect, useRef, useState } from "react";
import { useAudioLevels } from "@/hooks/use-audio-levels";

export const WAVEFORM_BAR_COUNT = 40;

const BAR_WIDTH_PX = 3;
const BAR_GAP_PX = 2;
const MIN_BAR_PERCENT = 12;

export function VoiceWaveform({ stream }: { stream: MediaStream | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [barCount, setBarCount] = useState(WAVEFORM_BAR_COUNT);
  const levels = useAudioLevels(stream, barCount);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver(([entry]) => {
      const fit = Math.floor(
        (entry.contentRect.width + BAR_GAP_PX) / (BAR_WIDTH_PX + BAR_GAP_PX),
      );
      setBarCount(Math.max(1, fit));
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label="音声の波形"
      className="flex h-8 flex-1 items-center justify-end gap-[2px] overflow-hidden"
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
