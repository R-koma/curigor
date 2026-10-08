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

interface HeldResponse {
  key: string | null;
  acceptsNext: boolean;
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
    hold,
    release,
    discardHeld,
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
  const heldRef = useRef<HeldResponse | null>(null);

  useEffect(() => {
    const was = enabledRef.current;
    enabledRef.current = enabled;
    if (enabled === was) return;
    if (liveKeyRef.current) skipRef.current = true;
    heldRef.current = null;
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
          const held = heldRef.current;
          if (held?.acceptsNext) {
            held.key = key;
            held.acceptsNext = false;
          } else if (held) {
            heldRef.current = null;
            discardHeld();
          }
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
        heldRef.current = null;
        stopPlayback();
      },
    });
  }, [bus, discardHeld, enqueue, stopPlayback]);

  const stop = useCallback(() => {
    if (liveKeyRef.current) skipRef.current = true;
    heldRef.current = null;
    stopPlayback();
  }, [stopPlayback]);

  const interrupt = useCallback(
    (includeUpcoming: boolean) => {
      if (heldRef.current) return;
      const key = liveKeyRef.current;
      heldRef.current = { key, acceptsNext: key === null && includeUpcoming };
      hold();
    },
    [hold],
  );

  const resumeInterrupted = useCallback(() => {
    if (!heldRef.current) return false;
    heldRef.current = null;
    release();
    return true;
  }, [release]);

  const discardInterrupted = useCallback(() => {
    const held = heldRef.current;
    if (!held) return;
    heldRef.current = null;
    if (held.acceptsNext) skipNextRef.current = true;
    else if (held.key !== null && liveKeyRef.current === held.key) {
      skipRef.current = true;
    }
    discardHeld();
  }, [discardHeld]);

  const playMessage = useCallback(
    (key: string, content: string) => {
      unlock();
      if (liveKeyRef.current) skipRef.current = true;
      heldRef.current = null;
      playAll(key, splitIntoSentences(content));
    },
    [playAll, unlock],
  );

  useEffect(() => stopPlayback, [stopPlayback]);

  return {
    stop,
    interrupt,
    resumeInterrupted,
    discardInterrupted,
    unlock,
    playMessage,
    activeKey,
    isSpeaking,
    error,
  };
}
