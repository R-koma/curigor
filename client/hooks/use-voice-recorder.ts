"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { transcribeAudio } from "@/lib/api";
import {
  AUDIO_BITS_PER_SECOND,
  MAX_RECORDING_SECONDS,
  pickRecordingMimeType,
  transcriptionErrorMessage,
} from "@/lib/audio";

export type VoiceStatus = "idle" | "recording" | "transcribing";

interface UseVoiceRecorderOptions {
  sessionId: string | null;
  onTranscript: (text: string) => void;
}

export interface VoiceRecorder {
  status: VoiceStatus;
  elapsedSeconds: number;
  error: string | null;
  canRetry: boolean;
  start: () => Promise<void>;
  stop: () => void;
  retry: () => Promise<void>;
}

export function useVoiceRecorder({
  sessionId,
  onTranscript,
}: UseVoiceRecorderOptions): VoiceRecorder {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [failedRecording, setFailedRecording] = useState<Blob | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onTranscriptRef = useRef(onTranscript);

  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  const transcribe = useCallback(
    async (recording: Blob) => {
      if (!sessionId) {
        setStatus("idle");
        return;
      }
      setStatus("transcribing");
      setError(null);
      try {
        const text = await transcribeAudio(sessionId, recording);
        setFailedRecording(null);
        if (text) onTranscriptRef.current(text);
        else setError("音声を聞き取れませんでした");
      } catch (err) {
        setFailedRecording(recording);
        setError(transcriptionErrorMessage(err));
      } finally {
        setStatus("idle");
      }
    },
    [sessionId],
  );

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }, []);

  const start = useCallback(async () => {
    setError(null);
    const mimeType = pickRecordingMimeType();
    if (!mimeType || !navigator.mediaDevices?.getUserMedia) {
      setError("このブラウザは音声入力に対応していません");
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("マイクの使用が許可されていません");
      return;
    }

    const recorder = new MediaRecorder(stream, {
      mimeType,
      audioBitsPerSecond: AUDIO_BITS_PER_SECOND,
    });
    const chunks: Blob[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      recorderRef.current = null;
      const recording = new Blob(chunks, { type: mimeType });
      if (recording.size === 0) {
        setStatus("idle");
        setError("録音が短すぎます");
        return;
      }
      void transcribe(recording);
    };

    recorderRef.current = recorder;
    recorder.start();
    setFailedRecording(null);
    setElapsedSeconds(0);
    setStatus("recording");

    const startedAt = Date.now();
    timerRef.current = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setElapsedSeconds(elapsed);
      if (elapsed >= MAX_RECORDING_SECONDS) stop();
    }, 250);
  }, [stop, transcribe]);

  const retry = useCallback(async () => {
    if (failedRecording) await transcribe(failedRecording);
  }, [failedRecording, transcribe]);

  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
      recorderRef.current?.stream.getTracks().forEach((track) => track.stop());
    },
    [],
  );

  return {
    status,
    elapsedSeconds,
    error,
    canRetry: failedRecording !== null && status === "idle",
    start,
    stop,
    retry,
  };
}
