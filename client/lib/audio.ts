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

const REWRITE_KEPT_RATIO = 0.25;

export function isRewrite(previous: string, next: string): boolean {
  if (!previous) return false;
  const limit = Math.min(previous.length, next.length);
  let prefix = 0;
  while (prefix < limit && previous[prefix] === next[prefix]) prefix++;
  let suffix = 0;
  while (
    suffix < limit - prefix &&
    previous[previous.length - 1 - suffix] === next[next.length - 1 - suffix]
  ) {
    suffix++;
  }
  return (prefix + suffix) / previous.length < REWRITE_KEPT_RATIO;
}

export const RECORDING_WARNING_SECONDS = 30;

export function recordingWarning(elapsedSeconds: number): string | null {
  const remaining = MAX_RECORDING_SECONDS - elapsedSeconds;
  if (remaining > RECORDING_WARNING_SECONDS) return null;
  return `あと ${Math.max(remaining, 0)} 秒で自動で確定します`;
}

export function transcriptionErrorMessage(err: unknown): string {
  if (err instanceof TranscriptionError) {
    if (err.status === 429) return "今日の音声入力の上限に達しました";
    if (err.status === 413) return "録音が長すぎます";
    if (err.status === 415) return "この形式の音声には対応していません";
  }
  return "文字起こしに失敗しました。再試行してください";
}
