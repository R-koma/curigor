"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAssistantSpeech } from "@/hooks/use-assistant-speech";
import { TranscriptionError, transcribeAudio } from "@/lib/api";
import { joinSegments, stripEndWord, turnIsComplete } from "@/lib/end-of-turn";
import {
  MicUnsupportedError,
  openMicCapture,
  type MicCapture,
  type OpenMic,
} from "@/lib/mic-capture";
import { FRAME_MS, concatSamples, frameLevel, type Samples } from "@/lib/pcm";
import type { SpeechBus } from "@/lib/speech-bus";
import { createSegmentedTranscriber } from "@/lib/stt/segmented";
import type {
  LiveTranscriber,
  SttMethod,
  TranscriptSegment,
} from "@/lib/stt/types";
import {
  DEFAULT_VAD_CONFIG,
  NOISE_CALIBRATION_MS,
  SPEAKING_START_MS,
  VoiceActivityDetector,
  thresholdFromNoise,
} from "@/lib/vad";

export type ConversationStatus =
  | "off"
  | "starting"
  | "listening"
  | "thinking"
  | "speaking"
  | "paused";
type BaseStatus = "off" | "starting" | "active" | "paused";

export const SPEECH_SPEEDS = [1, 1.25, 1.5] as const;
export type SpeechSpeed = (typeof SPEECH_SPEEDS)[number];
export const DEFAULT_SPEECH_SPEED: SpeechSpeed = 1.25;

export interface VoiceUtterance {
  content: string;
  rawTranscript: string;
  sttMethod: SttMethod;
  sttLatencyMs: number;
}

export const MIC_DENIED_MESSAGE = "マイクの使用が許可されていません";
export const MIC_UNSUPPORTED_MESSAGE =
  "このブラウザは音声対話に対応していません";
export const TRANSCRIPTION_LIMIT_MESSAGE =
  "今日の文字起こしの上限に達しました。テキストで続けてください";
export const VOICE_SEND_FAILED_MESSAGE =
  "送信できませんでした。接続を確認してください";
export const RESUME_AFTER_INTERRUPT_MS = 1500;

const PRE_ROLL_FRAMES = 300 / FRAME_MS;
const CALIBRATION_FRAMES = NOISE_CALIBRATION_MS / FRAME_MS;
const MAX_STT_LATENCY_MS = 600_000;
const SPEED_KEY = "voice-speed";

type Transcribe = (
  sessionId: string | null,
  wav: Blob,
  prompt: string,
) => Promise<string>;

const defaultTranscribe: Transcribe = (sessionId, wav, prompt) =>
  transcribeAudio(sessionId, wav, undefined, prompt);

function transcriptionPrompt(topic: string | null): string {
  const base = "話し終えたら「以上」と言って締めくくります。";
  return (topic ? `${base}トピック: ${topic}` : base).slice(0, 200);
}

function readSpeed(): SpeechSpeed {
  try {
    const stored = Number(localStorage.getItem(SPEED_KEY));
    return (SPEECH_SPEEDS as readonly number[]).includes(stored)
      ? (stored as SpeechSpeed)
      : DEFAULT_SPEECH_SPEED;
  } catch {
    return DEFAULT_SPEECH_SPEED;
  }
}

function writeSpeed(speed: SpeechSpeed) {
  try {
    localStorage.setItem(SPEED_KEY, String(speed));
  } catch {
    return;
  }
}

interface UseVoiceConversationOptions {
  sessionId: string | null;
  bus: SpeechBus;
  isResponding: boolean;
  holdForReview: boolean;
  topic: string | null;
  onSend: (utterance: VoiceUtterance) => boolean;
  onHold: (utterance: VoiceUtterance) => void;
  openMic?: OpenMic;
  transcribe?: Transcribe;
  now?: () => number;
}

export function useVoiceConversation({
  sessionId,
  bus,
  isResponding,
  holdForReview,
  topic,
  onSend,
  onHold,
  openMic = openMicCapture,
  transcribe = defaultTranscribe,
  now = () => performance.now(),
}: UseVoiceConversationOptions) {
  const [base, setBase] = useState<BaseStatus>("off");
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [speed, setSpeedState] = useState<SpeechSpeed>(DEFAULT_SPEECH_SPEED);

  const speech = useAssistantSpeech({
    sessionId,
    bus,
    enabled: base === "active" || base === "starting",
    speed,
  });

  const latest = useRef({
    sessionId,
    isResponding,
    holdForReview,
    topic,
    onSend,
    onHold,
    transcribe,
    now,
  });
  useEffect(() => {
    latest.current = {
      sessionId,
      isResponding,
      holdForReview,
      topic,
      onSend,
      onHold,
      transcribe,
      now,
    };
  });

  const speechRef = useRef(speech);
  useEffect(() => {
    speechRef.current = speech;
  });

  const micRef = useRef<MicCapture | null>(null);
  const vadRef = useRef(new VoiceActivityDetector());
  const preRollRef = useRef<Samples[]>([]);
  const calibrationRef = useRef<number[]>([]);
  const pausedRef = useRef(false);
  const turnEndRef = useRef(0);
  const forceSendRef = useRef(false);
  const startTokenRef = useRef(0);
  const startingRef = useRef(false);
  const evaluateRef = useRef<() => void>(() => {});
  const levelListenersRef = useRef(new Set<(level: number) => void>());
  const stopRef = useRef<() => void>(() => {});
  const interruptedRef = useRef(false);
  const quietAfterInterruptRef = useRef<number | null>(null);
  const maybeResumeRef = useRef<() => void>(() => {});

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSpeedState(readSpeed());
  }, []);

  const setSpeed = useCallback((next: SpeechSpeed) => {
    setSpeedState(next);
    writeSpeed(next);
  }, []);

  const transcriberRef = useRef<LiveTranscriber | null>(null);
  useEffect(() => {
    transcriberRef.current = createSegmentedTranscriber({
      transcribe: (wav) =>
        latest.current.transcribe(
          latest.current.sessionId,
          wav,
          transcriptionPrompt(latest.current.topic),
        ),
      onChange: setSegments,
      onError: (err) => {
        if (err instanceof TranscriptionError && err.status === 429) {
          stopRef.current();
          setError(TRANSCRIPTION_LIMIT_MESSAGE);
        }
      },
    });
  }, []);

  const clearInterrupt = useCallback(() => {
    interruptedRef.current = false;
    quietAfterInterruptRef.current = null;
  }, []);

  const buildUtterance = useCallback(
    (list: TranscriptSegment[]): VoiceUtterance | null => {
      const content = stripEndWord(joinSegments(list));
      if (!content) return null;
      return {
        content,
        rawTranscript: content,
        sttMethod: transcriberRef.current!.method,
        sttLatencyMs: Math.min(
          MAX_STT_LATENCY_MS,
          Math.max(0, Math.round(latest.current.now() - turnEndRef.current)),
        ),
      };
    },
    [],
  );

  const deliver = useCallback(
    (utterance: VoiceUtterance) => {
      speechRef.current.discardInterrupted();
      clearInterrupt();
      if (latest.current.holdForReview) {
        latest.current.onHold(utterance);
        stopRef.current();
        return;
      }
      if (!latest.current.onSend(utterance)) {
        forceSendRef.current = false;
        setError(VOICE_SEND_FAILED_MESSAGE);
        return;
      }
      setError(null);
      forceSendRef.current = false;
      transcriberRef.current!.reset();
    },
    [clearInterrupt],
  );

  const evaluate = useCallback(() => {
    if (vadRef.current.inSpeech || latest.current.isResponding) return;
    const list = transcriberRef.current!.segments();
    if (list.some((segment) => segment.status === "pending")) return;
    if (!forceSendRef.current && !turnIsComplete(list)) return;
    const utterance = buildUtterance(list);
    if (!utterance) {
      forceSendRef.current = false;
      transcriberRef.current!.reset();
      return;
    }
    deliver(utterance);
  }, [buildUtterance, deliver]);

  useEffect(() => {
    evaluateRef.current = evaluate;
  }, [evaluate]);

  const maybeResume = useCallback(() => {
    const quiet = quietAfterInterruptRef.current;
    if (!interruptedRef.current || quiet === null) return;
    if (quiet < RESUME_AFTER_INTERRUPT_MS) return;
    if (vadRef.current.inSpeech || forceSendRef.current) return;
    const list = transcriberRef.current!.segments();
    if (list.some((segment) => segment.status === "pending")) return;
    if (turnIsComplete(list)) return;
    clearInterrupt();
    if (speechRef.current.resumeInterrupted()) {
      transcriberRef.current!.reset();
    }
  }, [clearInterrupt]);

  useEffect(() => {
    maybeResumeRef.current = maybeResume;
  }, [maybeResume]);

  useEffect(() => {
    if (!isResponding) evaluateRef.current();
  }, [isResponding]);

  const handleFrame = useCallback((frame: Samples) => {
    if (pausedRef.current) return;
    const level = frameLevel(frame);
    for (const listener of levelListenersRef.current) listener(level);
    const vad = vadRef.current;
    preRollRef.current = [...preRollRef.current, frame].slice(-PRE_ROLL_FRAMES);

    if (calibrationRef.current.length < CALIBRATION_FRAMES) {
      calibrationRef.current.push(level);
      if (calibrationRef.current.length === CALIBRATION_FRAMES) {
        vad.configure({
          threshold: thresholdFromNoise(calibrationRef.current),
        });
      }
      return;
    }

    vad.configure({
      startMs: speechRef.current.isSpeaking
        ? SPEAKING_START_MS
        : DEFAULT_VAD_CONFIG.startMs,
    });
    const event = vad.push(level);
    if (event === "start") {
      if (speechRef.current.isSpeaking || latest.current.isResponding) {
        speechRef.current.interrupt(latest.current.isResponding);
        interruptedRef.current = true;
      }
      quietAfterInterruptRef.current = null;
      transcriberRef.current!.begin(concatSamples(preRollRef.current));
      return;
    }
    if (!vad.inSpeech && event !== "end") {
      if (quietAfterInterruptRef.current !== null) {
        quietAfterInterruptRef.current += FRAME_MS;
        maybeResumeRef.current();
      }
      return;
    }
    transcriberRef.current!.push(frame);
    if (event === "split") {
      void transcriberRef.current!.end().then(() => evaluateRef.current());
      transcriberRef.current!.begin(new Float32Array(0));
    }
    if (event === "end") {
      turnEndRef.current = latest.current.now();
      if (interruptedRef.current) quietAfterInterruptRef.current = 0;
      void transcriberRef.current!.end().then(() => {
        evaluateRef.current();
        maybeResumeRef.current();
      });
    }
  }, []);

  const closeMic = useCallback(() => {
    micRef.current?.close();
    micRef.current = null;
    vadRef.current.reset();
    preRollRef.current = [];
  }, []);

  const stop = useCallback(() => {
    closeMic();
    startTokenRef.current += 1;
    startingRef.current = false;
    forceSendRef.current = false;
    clearInterrupt();
    transcriberRef.current!.reset();
    pausedRef.current = false;
    speechRef.current.stop();
    setBase("off");
  }, [closeMic, clearInterrupt]);

  useEffect(() => {
    stopRef.current = stop;
  }, [stop]);

  const openCapture = useCallback(async () => {
    if (micRef.current || startingRef.current) return;
    speechRef.current.unlock();
    startingRef.current = true;
    const token = startTokenRef.current;
    setError(null);
    setBase("starting");
    pausedRef.current = false;
    calibrationRef.current = [];
    vadRef.current = new VoiceActivityDetector();
    let capture: MicCapture;
    try {
      capture = await openMic(handleFrame);
    } catch (err) {
      if (token !== startTokenRef.current) return;
      startingRef.current = false;
      forceSendRef.current = false;
      transcriberRef.current!.reset();
      setBase("off");
      setError(
        err instanceof MicUnsupportedError
          ? MIC_UNSUPPORTED_MESSAGE
          : MIC_DENIED_MESSAGE,
      );
      return;
    }
    if (token !== startTokenRef.current) {
      capture.close();
      return;
    }
    startingRef.current = false;
    micRef.current = capture;
    setBase("active");
  }, [handleFrame, openMic]);

  const start = openCapture;

  const pause = useCallback(() => {
    if (!micRef.current && !startingRef.current) return;
    if (startingRef.current) {
      startTokenRef.current += 1;
      startingRef.current = false;
    }
    if (vadRef.current.inSpeech) {
      turnEndRef.current = latest.current.now();
      void transcriberRef.current!.end();
    }
    closeMic();
    clearInterrupt();
    pausedRef.current = true;
    speechRef.current.stop();
    setBase("paused");
  }, [closeMic, clearInterrupt]);

  const resume = useCallback(async () => {
    if (!pausedRef.current || document.hidden) return;
    await openCapture();
  }, [openCapture]);

  const sendNow = useCallback(async () => {
    turnEndRef.current = latest.current.now();
    if (vadRef.current.inSpeech) {
      vadRef.current.reset();
      void transcriberRef.current!.end();
    }
    if (latest.current.isResponding) forceSendRef.current = true;
    await transcriberRef.current!.settled();
    if (latest.current.isResponding) {
      evaluateRef.current();
      return;
    }
    const utterance = buildUtterance(transcriberRef.current!.segments());
    if (utterance) deliver(utterance);
    else forceSendRef.current = false;
  }, [buildUtterance, deliver]);

  const subscribeLevel = useCallback((listener: (level: number) => void) => {
    levelListenersRef.current.add(listener);
    return () => {
      levelListenersRef.current.delete(listener);
    };
  }, []);

  const discard = useCallback(() => {
    vadRef.current.reset();
    forceSendRef.current = false;
    transcriberRef.current!.reset();
  }, []);

  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden) pause();
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () =>
      document.removeEventListener("visibilitychange", handleVisibility);
  }, [pause]);

  useEffect(
    () => () => {
      startTokenRef.current += 1;
      micRef.current?.close();
      transcriberRef.current?.reset();
    },
    [],
  );

  const status: ConversationStatus =
    base === "active"
      ? speech.isSpeaking
        ? "speaking"
        : isResponding
          ? "thinking"
          : "listening"
      : base;

  return {
    status,
    segments,
    speed,
    setSpeed,
    start,
    stop,
    pause,
    resume,
    sendNow,
    discard,
    subscribeLevel,
    playMessage: speech.playMessage,
    stopSpeech: speech.stop,
    activeKey: speech.activeKey,
    error,
    speechError: speech.error,
  };
}
