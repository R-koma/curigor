"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SpeechError, synthesizeSpeech } from "@/lib/api";

const LOOKAHEAD = 2;

interface QueueItem {
  text: string;
  buffer?: Promise<AudioBuffer | null>;
}

interface UseSpeechPlaybackOptions {
  sessionId: string | null;
}

export function useSpeechPlayback({ sessionId }: UseSpeechPlaybackOptions) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionIdRef = useRef(sessionId);
  const contextRef = useRef<AudioContext | null>(null);
  const queueRef = useRef<QueueItem[]>([]);
  const playingRef = useRef(false);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const generationRef = useRef(0);
  const controllerRef = useRef(new AbortController());
  const limitedRef = useRef(false);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const load = useCallback(
    async (text: string): Promise<AudioBuffer | null> => {
      const context = contextRef.current;
      const id = sessionIdRef.current;
      if (!context || !id) return null;
      const { signal } = controllerRef.current;
      try {
        const data = await synthesizeSpeech(id, text, signal);
        return await context.decodeAudioData(data);
      } catch (err) {
        if (signal.aborted) return null;
        if (err instanceof SpeechError && err.status === 429) {
          limitedRef.current = true;
          queueRef.current = [];
          setError("今日の読み上げの上限に達しました");
        } else {
          setError("読み上げに失敗しました");
        }
        return null;
      }
    },
    [],
  );

  const prefetch = useCallback(() => {
    for (const item of queueRef.current.slice(0, LOOKAHEAD)) {
      item.buffer ??= load(item.text);
    }
  }, [load]);

  const playNextRef = useRef<() => Promise<void>>(async () => {});

  const playNext = useCallback(async () => {
    if (playingRef.current) return;
    const item = queueRef.current[0];
    if (!item) {
      setIsSpeaking(false);
      return;
    }
    playingRef.current = true;
    setIsSpeaking(true);
    const generation = generationRef.current;
    prefetch();
    const buffer = await item.buffer;
    if (generation !== generationRef.current) return;
    queueRef.current = queueRef.current.filter((queued) => queued !== item);
    const context = contextRef.current;
    if (buffer && context) {
      await new Promise<void>((resolve) => {
        const source = context.createBufferSource();
        source.buffer = buffer;
        source.connect(context.destination);
        source.onended = () => resolve();
        sourceRef.current = source;
        source.start();
      });
      if (generation !== generationRef.current) return;
    }
    playingRef.current = false;
    void playNextRef.current();
  }, [prefetch]);

  useEffect(() => {
    playNextRef.current = playNext;
  }, [playNext]);

  const enqueue = useCallback(
    (text: string) => {
      if (limitedRef.current || !contextRef.current) return;
      queueRef.current.push({ text });
      prefetch();
      void playNext();
    },
    [playNext, prefetch],
  );

  const stop = useCallback(() => {
    generationRef.current += 1;
    controllerRef.current.abort();
    controllerRef.current = new AbortController();
    queueRef.current = [];
    playingRef.current = false;
    sourceRef.current?.stop();
    sourceRef.current = null;
    setIsSpeaking(false);
    if (!limitedRef.current) setError(null);
  }, []);

  const unlock = useCallback(() => {
    contextRef.current ??= new AudioContext();
    if (contextRef.current.state === "suspended") {
      void contextRef.current.resume();
    }
  }, []);

  return { enqueue, stop, unlock, isSpeaking, error };
}
