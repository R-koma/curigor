"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SpeechError, synthesizeSpeech } from "@/lib/api";

const LOOKAHEAD = 2;
const RESUME_TIMEOUT_MS = 300;
export const MAX_CACHED_RESPONSES = 20;

export const SPEECH_FAILED_MESSAGE = "読み上げに失敗しました";
export const SPEECH_LIMIT_MESSAGE = "今日の読み上げの上限に達しました";
export const SPEECH_INTERRUPTED_MESSAGE =
  "再生が中断されました。▶ で聞き直せます";

export interface SpokenSentence {
  key: string;
  index: number;
  text: string;
}

type Audio = Promise<ArrayBuffer | null>;

interface QueueItem extends SpokenSentence {
  audio?: Audio;
}

interface InflightRequest {
  key: string;
  index: number;
  audio: Audio;
}

function isRunning(context: AudioContext): boolean {
  return context.state === "running";
}

async function ensureRunning(context: AudioContext): Promise<boolean> {
  if (isRunning(context)) return true;
  await Promise.race([
    context.resume().catch(() => undefined),
    new Promise((resolve) => setTimeout(resolve, RESUME_TIMEOUT_MS)),
  ]);
  return isRunning(context);
}

interface UseSpeechPlaybackOptions {
  sessionId: string | null;
}

export function useSpeechPlayback({ sessionId }: UseSpeechPlaybackOptions) {
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sessionIdRef = useRef(sessionId);
  const contextRef = useRef<AudioContext | null>(null);
  const queueRef = useRef<QueueItem[]>([]);
  const cacheRef = useRef(new Map<string, Map<number, Audio>>());
  const inflightRef = useRef(new Set<InflightRequest>());
  const playingRef = useRef(false);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const generationRef = useRef(0);
  const controllerRef = useRef(new AbortController());
  const limitedRef = useRef(false);
  const playNextRef = useRef<() => Promise<void>>(async () => {});

  const cached = useCallback(
    (key: string, index: number) => cacheRef.current.get(key)?.get(index),
    [],
  );

  const remember = useCallback((key: string, index: number, audio: Audio) => {
    const cache = cacheRef.current;
    const sentences = cache.get(key) ?? new Map<number, Audio>();
    cache.delete(key);
    cache.set(key, sentences);
    sentences.set(index, audio);
    while (cache.size > MAX_CACHED_RESPONSES) {
      const oldest = cache.keys().next().value;
      if (oldest === undefined) break;
      cache.delete(oldest);
    }
  }, []);

  const forget = useCallback((key: string, index: number, audio: Audio) => {
    const sentences = cacheRef.current.get(key);
    if (sentences?.get(index) === audio) sentences.delete(index);
  }, []);

  const fetchAudio = useCallback(
    (item: SpokenSentence): Audio | undefined => {
      const hit = cached(item.key, item.index);
      if (hit) return hit;
      const id = sessionIdRef.current;
      if (!id || limitedRef.current) return undefined;
      const { signal } = controllerRef.current;
      const audio: Audio = synthesizeSpeech(id, item.text, signal).catch(
        (err: unknown) => {
          forget(item.key, item.index, audio);
          if (signal.aborted) return null;
          if (err instanceof SpeechError && err.status === 429) {
            limitedRef.current = true;
            queueRef.current = [];
            setError(SPEECH_LIMIT_MESSAGE);
          } else {
            setError(SPEECH_FAILED_MESSAGE);
          }
          return null;
        },
      );
      remember(item.key, item.index, audio);
      const request = { key: item.key, index: item.index, audio };
      inflightRef.current.add(request);
      void audio.finally(() => inflightRef.current.delete(request));
      return audio;
    },
    [cached, forget, remember],
  );

  const prefetch = useCallback(() => {
    for (const item of queueRef.current.slice(0, LOOKAHEAD)) {
      item.audio ??= fetchAudio(item);
    }
  }, [fetchAudio]);

  const finish = useCallback(() => {
    playingRef.current = false;
    setActiveKey(null);
  }, []);

  const playNext = useCallback(async () => {
    if (playingRef.current) return;
    const item = queueRef.current[0];
    if (!item) {
      finish();
      return;
    }
    prefetch();
    if (!item.audio && !sessionIdRef.current) return;
    playingRef.current = true;
    setActiveKey(item.key);
    const generation = generationRef.current;
    item.audio ??= fetchAudio(item);
    const data = item.audio ? await item.audio : null;
    if (generation !== generationRef.current) return;
    queueRef.current = queueRef.current.filter((queued) => queued !== item);
    const context = contextRef.current;
    if (data && context) {
      const running = await ensureRunning(context);
      if (generation !== generationRef.current) return;
      if (!running) {
        queueRef.current = [];
        finish();
        setError(SPEECH_INTERRUPTED_MESSAGE);
        return;
      }
      let buffer: AudioBuffer | null = null;
      try {
        buffer = await context.decodeAudioData(data.slice(0));
      } catch {
        setError(SPEECH_FAILED_MESSAGE);
      }
      if (generation !== generationRef.current) return;
      if (buffer) {
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
    }
    playingRef.current = false;
    void playNextRef.current();
  }, [fetchAudio, finish, prefetch]);

  useEffect(() => {
    playNextRef.current = playNext;
  }, [playNext]);

  useEffect(() => {
    sessionIdRef.current = sessionId;
    if (sessionId) void playNextRef.current();
  }, [sessionId]);

  const enqueue = useCallback(
    (key: string, index: number, text: string) => {
      if (!contextRef.current) return;
      if (limitedRef.current && !cached(key, index)) return;
      queueRef.current.push({ key, index, text });
      prefetch();
      void playNext();
    },
    [cached, playNext, prefetch],
  );

  const stop = useCallback(() => {
    generationRef.current += 1;
    controllerRef.current.abort();
    controllerRef.current = new AbortController();
    inflightRef.current.forEach(({ key, index, audio }) =>
      forget(key, index, audio),
    );
    inflightRef.current.clear();
    queueRef.current = [];
    playingRef.current = false;
    sourceRef.current?.stop();
    sourceRef.current = null;
    setActiveKey(null);
    if (!limitedRef.current) setError(null);
  }, [forget]);

  const playAll = useCallback(
    (key: string, sentences: string[]) => {
      stop();
      sentences.forEach((text, index) => enqueue(key, index, text));
    },
    [enqueue, stop],
  );

  const unlock = useCallback(() => {
    contextRef.current ??= new AudioContext();
    if (contextRef.current.state === "suspended") {
      void contextRef.current.resume();
    }
  }, []);

  const resetLimit = useCallback(() => {
    limitedRef.current = false;
    setError(null);
  }, []);

  useEffect(
    () => () => {
      generationRef.current += 1;
      controllerRef.current.abort();
      controllerRef.current = new AbortController();
      queueRef.current = [];
      playingRef.current = false;
      sourceRef.current?.stop();
      sourceRef.current = null;
      void contextRef.current?.close();
      contextRef.current = null;
    },
    [],
  );

  return {
    enqueue,
    playAll,
    stop,
    unlock,
    resetLimit,
    activeKey,
    isSpeaking: activeKey !== null,
    error,
  };
}
