"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSpeechPlayback } from "@/hooks/use-speech-playback";
import type { SpeechBus } from "@/lib/speech-bus";
import { SentenceSplitter, splitIntoSentences } from "@/lib/speech-text";

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
    playAll,
    stop: stopPlayback,
    unlock,
    resetLimit,
    current,
    activeKey,
    isSpeaking,
    error,
  } = useSpeechPlayback({ sessionId });
  const enabledRef = useRef(false);
  const splitterRef = useRef(new SentenceSplitter());
  const liveKeyRef = useRef<string | null>(null);
  const indexRef = useRef(0);
  const skipRef = useRef(false);

  useEffect(() => {
    const stored = readStored();
    enabledRef.current = stored;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEnabledState(stored);
  }, []);

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
        }
        speak(splitterRef.current.push(text));
      },
      onEnd: () => {
        speak(splitterRef.current.flush());
        reset();
      },
      onAbort: () => {
        reset();
        stopPlayback();
      },
    });
  }, [bus, enqueue, stopPlayback]);

  const stop = useCallback(() => {
    if (liveKeyRef.current) skipRef.current = true;
    stopPlayback();
  }, [stopPlayback]);

  const interrupt = useCallback(() => {
    if (enabledRef.current) unlock();
    stop();
  }, [stop, unlock]);

  const setEnabled = useCallback(
    (next: boolean) => {
      enabledRef.current = next;
      setEnabledState(next);
      writeStored(next);
      if (next) {
        unlock();
        resetLimit();
        if (liveKeyRef.current) skipRef.current = true;
      } else {
        stop();
      }
    },
    [resetLimit, stop, unlock],
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
    enabled,
    setEnabled,
    stop,
    interrupt,
    playMessage,
    current,
    activeKey,
    isSpeaking,
    error,
  };
}
