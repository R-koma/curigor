"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SPEECH_SAMPLE_RATE, SpeechError, streamSpeech } from "@/lib/api";
import type { Samples } from "@/lib/pcm";
import { SentenceAudio, readPcm16 } from "@/lib/pcm-stream";

const LOOKAHEAD = 2;
const RESUME_TIMEOUT_MS = 300;
const START_DELAY_SECONDS = 0.05;
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

interface QueueItem extends SpokenSentence {
  audio?: SentenceAudio;
}

interface InflightRequest {
  key: string;
  index: number;
  audio: SentenceAudio;
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
  speed?: number;
  onPlaybackStart?: (key: string, index: number) => void;
}

export function useSpeechPlayback({
  sessionId,
  speed = 1,
  onPlaybackStart,
}: UseSpeechPlaybackOptions) {
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sessionIdRef = useRef(sessionId);
  const speedRef = useRef(speed);
  const onPlaybackStartRef = useRef(onPlaybackStart);
  const contextRef = useRef<AudioContext | null>(null);
  const queueRef = useRef<QueueItem[]>([]);
  const cacheRef = useRef(new Map<string, Map<number, SentenceAudio>>());
  const inflightRef = useRef(new Set<InflightRequest>());
  const sourcesRef = useRef(new Set<AudioBufferSourceNode>());
  const nextStartRef = useRef(0);
  const playingRef = useRef(false);
  const generationRef = useRef(0);
  const controllerRef = useRef(new AbortController());
  const limitedRef = useRef(false);
  const playNextRef = useRef<() => Promise<void>>(async () => {});
  const prefetchRef = useRef<() => void>(() => {});

  useEffect(() => {
    onPlaybackStartRef.current = onPlaybackStart;
  }, [onPlaybackStart]);

  useEffect(() => {
    if (speedRef.current === speed) return;
    speedRef.current = speed;
    cacheRef.current.clear();
  }, [speed]);

  const cached = useCallback(
    (key: string, index: number) => cacheRef.current.get(key)?.get(index),
    [],
  );

  const remember = useCallback(
    (key: string, index: number, audio: SentenceAudio) => {
      const cache = cacheRef.current;
      const sentences = cache.get(key) ?? new Map<number, SentenceAudio>();
      cache.delete(key);
      cache.set(key, sentences);
      sentences.set(index, audio);
      while (cache.size > MAX_CACHED_RESPONSES) {
        const oldest = cache.keys().next().value;
        if (oldest === undefined) break;
        cache.delete(oldest);
      }
    },
    [],
  );

  const forget = useCallback(
    (key: string, index: number, audio: SentenceAudio) => {
      const sentences = cacheRef.current.get(key);
      if (sentences?.get(index) === audio) sentences.delete(index);
    },
    [],
  );

  const fetchAudio = useCallback(
    (item: SpokenSentence): SentenceAudio | undefined => {
      const hit = cached(item.key, item.index);
      if (hit) return hit;
      const id = sessionIdRef.current;
      if (!id || limitedRef.current) return undefined;
      const { signal } = controllerRef.current;
      const audio = new SentenceAudio();
      remember(item.key, item.index, audio);
      const request = { key: item.key, index: item.index, audio };
      inflightRef.current.add(request);
      void (async () => {
        try {
          const body = await streamSpeech(
            id,
            item.text,
            speedRef.current,
            signal,
          );
          await readPcm16(body, (chunk) => audio.push(chunk));
          audio.finish(true);
        } catch (err) {
          forget(item.key, item.index, audio);
          if (!signal.aborted) {
            if (err instanceof SpeechError && err.status === 429) {
              limitedRef.current = true;
              queueRef.current = [];
              setError(SPEECH_LIMIT_MESSAGE);
            } else {
              setError(SPEECH_FAILED_MESSAGE);
            }
          }
          audio.finish(false);
        } finally {
          inflightRef.current.delete(request);
          prefetchRef.current();
        }
      })();
      return audio;
    },
    [cached, forget, remember],
  );

  const prefetch = useCallback(() => {
    for (const item of queueRef.current.slice(0, LOOKAHEAD)) {
      if (item.audio) continue;
      if (
        !cached(item.key, item.index) &&
        inflightRef.current.size >= LOOKAHEAD
      ) {
        break;
      }
      item.audio = fetchAudio(item);
    }
  }, [cached, fetchAudio]);

  useEffect(() => {
    prefetchRef.current = prefetch;
  }, [prefetch]);

  const settleIfIdle = useCallback(() => {
    if (
      !playingRef.current &&
      queueRef.current.length === 0 &&
      sourcesRef.current.size === 0
    ) {
      setActiveKey(null);
    }
  }, []);

  const playStream = useCallback(
    (
      context: AudioContext,
      item: SpokenSentence,
      audio: SentenceAudio,
      generation: number,
    ) =>
      new Promise<void>((resolve) => {
        let first = true;
        const schedule = (chunk: Samples) => {
          if (generation !== generationRef.current || chunk.length === 0)
            return;
          const buffer = context.createBuffer(
            1,
            chunk.length,
            SPEECH_SAMPLE_RATE,
          );
          buffer.copyToChannel(chunk, 0);
          const source = context.createBufferSource();
          source.buffer = buffer;
          source.connect(context.destination);
          source.onended = () => {
            sourcesRef.current.delete(source);
            if (generation === generationRef.current) settleIfIdle();
          };
          const startAt = Math.max(
            nextStartRef.current,
            context.currentTime + START_DELAY_SECONDS,
          );
          sourcesRef.current.add(source);
          source.start(startAt);
          nextStartRef.current = startAt + buffer.duration;
          if (first) {
            first = false;
            onPlaybackStartRef.current?.(item.key, item.index);
          }
        };
        audio.chunks.forEach(schedule);
        const unsubscribe = audio.subscribe(schedule);
        void audio.done.then(() => {
          unsubscribe();
          resolve();
        });
      }),
    [settleIfIdle],
  );

  const playNext = useCallback(async () => {
    if (playingRef.current) return;
    const item = queueRef.current[0];
    if (!item) {
      settleIfIdle();
      return;
    }
    prefetch();
    if (!item.audio && !sessionIdRef.current) return;
    playingRef.current = true;
    setActiveKey(item.key);
    const generation = generationRef.current;
    item.audio ??= fetchAudio(item);
    queueRef.current = queueRef.current.filter((queued) => queued !== item);
    prefetch();
    const context = contextRef.current;
    if (item.audio && context) {
      const running = await ensureRunning(context);
      if (generation !== generationRef.current) return;
      if (!running) {
        queueRef.current = [];
        playingRef.current = false;
        setActiveKey(null);
        setError(SPEECH_INTERRUPTED_MESSAGE);
        return;
      }
      await playStream(context, item, item.audio, generation);
      if (generation !== generationRef.current) return;
    }
    playingRef.current = false;
    void playNextRef.current();
  }, [fetchAudio, playStream, prefetch, settleIfIdle]);

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

  const silenceSources = useCallback(() => {
    sourcesRef.current.forEach((source) => {
      source.onended = null;
      try {
        source.stop();
      } catch {
        return;
      }
    });
    sourcesRef.current.clear();
    nextStartRef.current = 0;
  }, []);

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
    silenceSources();
    setActiveKey(null);
    if (!limitedRef.current) setError(null);
  }, [forget, silenceSources]);

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
      silenceSources();
      void contextRef.current?.close();
      contextRef.current = null;
    },
    [silenceSources],
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
