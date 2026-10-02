import { TranscriptionError } from "@/lib/api";

export const MAX_RECORDING_SECONDS = 300;
export const AUDIO_BITS_PER_SECOND = 64_000;

const RECORDING_MIME_TYPES = ["audio/webm;codecs=opus", "audio/mp4"];

export function pickRecordingMimeType(): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  return (
    RECORDING_MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type)) ??
    null
  );
}

export function appendTranscript(current: string, transcript: string): string {
  if (!current.trim()) return transcript;
  return `${current.trimEnd()}\n${transcript}`;
}

export function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

export function transcriptionErrorMessage(err: unknown): string {
  if (err instanceof TranscriptionError) {
    if (err.status === 429) return "今日の音声入力の上限に達しました";
    if (err.status === 413) return "録音が長すぎます";
    if (err.status === 415) return "この形式の音声には対応していません";
  }
  return "文字起こしに失敗しました。再試行してください";
}
