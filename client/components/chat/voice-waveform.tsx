"use client";

import { useEffect, useRef, useState } from "react";
import { visibleLevels } from "@/lib/audio-levels";

export const WAVEFORM_BAR_COUNT = 40;

const BAR_WIDTH_PX = 3;
const BAR_GAP_PX = 2;
const MIN_BAR_PERCENT = 12;
const QUIET_LEVEL = 0.05;

export function VoiceWaveform({ history }: { history: number[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [barCount, setBarCount] = useState(WAVEFORM_BAR_COUNT);

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
      className="flex h-8 flex-1 items-center justify-end gap-[2px] overflow-hidden [mask-image:linear-gradient(to_right,transparent,#000_32px)]"
    >
      {visibleLevels(history, barCount).map((level, i) => (
        <span
          key={i}
          className={`w-[3px] shrink-0 rounded-full motion-safe:transition-[height] motion-safe:duration-75 ${
            level < QUIET_LEVEL ? "bg-foreground/30" : "bg-foreground/70"
          }`}
          style={{
            height: `${Math.max(MIN_BAR_PERCENT, Math.round(level * 100))}%`,
          }}
        />
      ))}
    </div>
  );
}
