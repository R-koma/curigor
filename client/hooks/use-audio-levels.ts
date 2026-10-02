"use client";

import { useEffect, useState } from "react";
import { LEVEL_INTERVAL_MS, pushLevel, rmsLevel } from "@/lib/audio-levels";

export function useAudioLevels(
  stream: MediaStream | null,
  count: number,
): number[] {
  const [levels, setLevels] = useState<number[]>(() =>
    Array.from({ length: count }, () => 0),
  );

  useEffect(() => {
    if (!stream || typeof AudioContext === "undefined") return;

    const context = new AudioContext();
    if (context.state === "suspended") void context.resume();
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    const source = context.createMediaStreamSource(stream);
    source.connect(analyser);
    const samples = new Uint8Array(analyser.fftSize);

    const timer = setInterval(() => {
      analyser.getByteTimeDomainData(samples);
      setLevels((prev) => pushLevel(prev, rmsLevel(samples)));
    }, LEVEL_INTERVAL_MS);

    return () => {
      clearInterval(timer);
      source.disconnect();
      void context.close();
    };
  }, [stream]);

  return levels;
}
