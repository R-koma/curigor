"use client";

import { useEffect, useState } from "react";
import {
  LEVEL_INTERVAL_MS,
  REDUCED_MOTION_LEVEL_INTERVAL_MS,
  pushLevel,
  rmsLevel,
} from "@/lib/audio-levels";

function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function useAudioLevels(
  stream: MediaStream | null,
  count: number,
): number[] {
  const [levels, setLevels] = useState<number[]>(() =>
    Array.from({ length: count }, () => 0),
  );

  useEffect(() => {
    if (!stream || typeof AudioContext === "undefined") return;

    let context: AudioContext | null = null;
    let source: MediaStreamAudioSourceNode | null = null;
    let analyser: AnalyserNode;
    try {
      context = new AudioContext();
      if (context.state === "suspended") context.resume().catch(() => {});
      analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      source = context.createMediaStreamSource(stream);
      source.connect(analyser);
    } catch {
      source?.disconnect();
      context?.close().catch(() => {});
      return;
    }

    const samples = new Uint8Array(analyser.fftSize);
    const timer = setInterval(
      () => {
        analyser.getByteTimeDomainData(samples);
        setLevels((prev) => pushLevel(prev, rmsLevel(samples)));
      },
      prefersReducedMotion()
        ? REDUCED_MOTION_LEVEL_INTERVAL_MS
        : LEVEL_INTERVAL_MS,
    );

    return () => {
      clearInterval(timer);
      source?.disconnect();
      context?.close().catch(() => {});
    };
  }, [stream]);

  return levels;
}
