"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { transcribeAudio } from "@/lib/api";
import {
  AUDIO_BITS_PER_SECOND,
  MAX_RECORDING_SECONDS,
  pickRecordingMimeType,
  transcriptionErrorMessage,
} from "@/lib/audio";

export type VoiceStatus =
  | "idle"
  | "starting"
  | "recording"
  | "stopping"
  | "transcribing";

interface UseVoiceRecorderOptions {
  sessionId: string | null;
  onTranscript: (text: string) => void;
}

export interface VoiceRecorder {
  status: VoiceStatus;
  elapsedSeconds: number;
  error: string | null;
  canRetry: boolean;
  stream: MediaStream | null;
  start: () => Promise<void>;
  stop: () => void;
  cancel: () => void;
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
  const [stream, setStream] = useState<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  const startingRef = useRef(false);
  const disposedRef = useRef(false);
  const cancelledRef = useRef(false);

  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  const transcribe = useCallback(
    async (recording: Blob) => {
      setStatus("transcribing");
      setError(null);
      try {
        const text = await transcribeAudio(sessionId, recording);
        if (disposedRef.current) return;
        setFailedRecording(null);
        if (text) onTranscriptRef.current(text);
        else setError("音声を聞き取れませんでした");
      } catch (err) {
        if (disposedRef.current) return;
        setFailedRecording(recording);
        setError(transcriptionErrorMessage(err));
      } finally {
        if (!disposedRef.current) setStatus("idle");
      }
    },
    [sessionId],
  );

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (recorderRef.current?.state !== "recording") return;
    setStatus("stopping");
    recorderRef.current.stop();
  }, []);

  const cancel = useCallback(() => {
    if (recorderRef.current?.state !== "recording") return;
    cancelledRef.current = true;
    stop();
  }, [stop]);

  const start = useCallback(async () => {
    if (startingRef.current || recorderRef.current) return;
    setError(null);
    const mimeType = pickRecordingMimeType();
    if (!mimeType || !navigator.mediaDevices?.getUserMedia) {
      setError("このブラウザは音声入力に対応していません");
      return;
    }

    startingRef.current = true;
    setStatus("starting");
    let mediaStream: MediaStream;
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      startingRef.current = false;
      setStatus("idle");
      setError("マイクの使用が許可されていません");
      return;
    }
    if (disposedRef.current) {
      mediaStream.getTracks().forEach((track) => track.stop());
      startingRef.current = false;
      return;
    }

    const abortStart = () => {
      mediaStream.getTracks().forEach((track) => track.stop());
      recorderRef.current = null;
      startingRef.current = false;
      setStatus("idle");
      setError("録音を開始できませんでした");
    };

    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(mediaStream, {
        mimeType,
        audioBitsPerSecond: AUDIO_BITS_PER_SECOND,
      });
    } catch {
      abortStart();
      return;
    }
    const chunks: Blob[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = () => {
      mediaStream.getTracks().forEach((track) => track.stop());
      recorderRef.current = null;
      setStream(null);
      if (cancelledRef.current) {
        cancelledRef.current = false;
        setStatus("idle");
        return;
      }
      const recording = new Blob(chunks, { type: mimeType });
      if (recording.size === 0) {
        setStatus("idle");
        setError("録音が短すぎます");
        return;
      }
      void transcribe(recording);
    };

    recorderRef.current = recorder;
    startingRef.current = false;
    cancelledRef.current = false;
    try {
      recorder.start();
    } catch {
      abortStart();
      return;
    }
    setStream(mediaStream);
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

  useEffect(() => {
    disposedRef.current = false;
    return () => {
      disposedRef.current = true;
      if (timerRef.current) clearInterval(timerRef.current);
      const recorder = recorderRef.current;
      if (recorder) {
        recorder.ondataavailable = null;
        recorder.onstop = null;
        recorder.stream.getTracks().forEach((track) => track.stop());
      }
      recorderRef.current = null;
    };
  }, []);

  return {
    status,
    elapsedSeconds,
    error,
    canRetry: failedRecording !== null && status === "idle",
    stream,
    start,
    stop,
    cancel,
    retry,
  };
}
