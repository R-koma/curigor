"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSpeechPlayback } from "@/hooks/use-speech-playback";
import type { SpeechBus } from "@/lib/speech-bus";
import { SentenceSplitter } from "@/lib/speech-text";

const STORAGE_KEY = "voice-mode";

function readStored(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeStored(enabled: boolean) {
  try {
    localStorage.setItem(STORAGE_KEY, enabled ? "1" : "0");
  } catch {
    return;
  }
}

interface UseVoiceModeOptions {
  sessionId: string | null;
  bus: SpeechBus;
}

export function useVoiceMode({ sessionId, bus }: UseVoiceModeOptions) {
  const [enabled, setEnabledState] = useState(false);
  const {
    enqueue,
    stop: stopPlayback,
    unlock,
    isSpeaking,
    error,
  } = useSpeechPlayback({ sessionId });
  const enabledRef = useRef(false);
  const splitterRef = useRef(new SentenceSplitter());
  const streamingRef = useRef(false);
  const skipRef = useRef(false);

  useEffect(() => {
    const stored = readStored();
    enabledRef.current = stored;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEnabledState(stored);
  }, []);

  useEffect(
    () =>
      bus.subscribe({
        onText: (text) => {
          streamingRef.current = true;
          if (!enabledRef.current || skipRef.current) return;
          splitterRef.current
            .push(text)
            .forEach((sentence) => enqueue(sentence));
        },
        onEnd: () => {
          if (enabledRef.current && !skipRef.current) {
            splitterRef.current
              .flush()
              .forEach((sentence) => enqueue(sentence));
          }
          splitterRef.current = new SentenceSplitter();
          streamingRef.current = false;
          skipRef.current = false;
        },
      }),
    [bus, enqueue],
  );

  const stop = useCallback(() => {
    if (streamingRef.current) skipRef.current = true;
    splitterRef.current = new SentenceSplitter();
    stopPlayback();
  }, [stopPlayback]);

  const interrupt = useCallback(() => {
    unlock();
    stop();
  }, [stop, unlock]);

  const setEnabled = useCallback(
    (next: boolean) => {
      enabledRef.current = next;
      setEnabledState(next);
      writeStored(next);
      if (next) {
        unlock();
        if (streamingRef.current) skipRef.current = true;
      } else {
        stop();
      }
    },
    [stop, unlock],
  );

  useEffect(() => stopPlayback, [stopPlayback]);

  return { enabled, setEnabled, stop, interrupt, isSpeaking, error };
}
