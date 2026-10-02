"use client";

import { useEffect, useState } from "react";
import { levelIntervalMs, pushLevel, rmsLevel } from "@/lib/audio-levels";

export function useAudioHistory(stream: MediaStream | null): number[] {
  const [history, setHistory] = useState<number[]>([]);

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
    const timer = setInterval(() => {
      analyser.getByteTimeDomainData(samples);
      setHistory((prev) => pushLevel(prev, rmsLevel(samples)));
    }, levelIntervalMs());

    return () => {
      clearInterval(timer);
      source?.disconnect();
      context?.close().catch(() => {});
    };
  }, [stream]);

  return history;
}
