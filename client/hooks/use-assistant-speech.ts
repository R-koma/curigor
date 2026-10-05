"use client";

import { useCallback, useEffect, useRef } from "react";
import { useSpeechPlayback } from "@/hooks/use-speech-playback";
import type { SpeechBus } from "@/lib/speech-bus";
import { SentenceSplitter, splitIntoSentences } from "@/lib/speech-text";

interface UseAssistantSpeechOptions {
  sessionId: string | null;
  bus: SpeechBus;
  enabled: boolean;
  speed: number;
  onPlaybackStart?: (key: string, index: number) => void;
}

export function useAssistantSpeech({
  sessionId,
  bus,
  enabled,
  speed,
  onPlaybackStart,
}: UseAssistantSpeechOptions) {
  const {
    enqueue,
    playAll,
    stop: stopPlayback,
    unlock,
    resetLimit,
    activeKey,
    isSpeaking,
    error,
  } = useSpeechPlayback({ sessionId, speed, onPlaybackStart });
  const enabledRef = useRef(enabled);
  const splitterRef = useRef(new SentenceSplitter());
  const liveKeyRef = useRef<string | null>(null);
  const indexRef = useRef(0);
  const skipRef = useRef(false);
  const skipNextRef = useRef(false);

  useEffect(() => {
    const was = enabledRef.current;
    enabledRef.current = enabled;
    if (enabled === was) return;
    if (liveKeyRef.current) skipRef.current = true;
    if (enabled) resetLimit();
    else stopPlayback();
  }, [enabled, resetLimit, stopPlayback]);

  useEffect(() => {
    const reset = () => {
      splitterRef.current = new SentenceSplitter();
      liveKeyRef.current = null;
      indexRef.current = 0;
      skipRef.current = false;
    };
    const speak = (sentences: string[]) => {
      const key = liveKeyRef.current;
      for (const sentence of sentences) {
        const index = indexRef.current++;
        if (key && enabledRef.current && !skipRef.current) {
          enqueue(key, index, sentence);
        }
      }
    };
    return bus.subscribe({
      onText: (key, text) => {
        if (liveKeyRef.current !== key) {
          reset();
          liveKeyRef.current = key;
          if (skipNextRef.current) {
            skipRef.current = true;
            skipNextRef.current = false;
          }
        }
        speak(splitterRef.current.push(text));
      },
      onEnd: () => {
        speak(splitterRef.current.flush());
        if (!liveKeyRef.current) skipNextRef.current = false;
        reset();
      },
      onAbort: () => {
        reset();
        skipNextRef.current = false;
        stopPlayback();
      },
    });
  }, [bus, enqueue, stopPlayback]);

  const stop = useCallback(() => {
    if (liveKeyRef.current) skipRef.current = true;
    stopPlayback();
  }, [stopPlayback]);

  const silence = useCallback(
    (includeUpcoming: boolean) => {
      if (liveKeyRef.current) skipRef.current = true;
      else if (includeUpcoming) skipNextRef.current = true;
      stopPlayback();
    },
    [stopPlayback],
  );

  const playMessage = useCallback(
    (key: string, content: string) => {
      unlock();
      if (liveKeyRef.current) skipRef.current = true;
      playAll(key, splitIntoSentences(content));
    },
    [playAll, unlock],
  );

  useEffect(() => stopPlayback, [stopPlayback]);

  return {
    stop,
    silence,
    unlock,
    playMessage,
    activeKey,
    isSpeaking,
    error,
  };
}
