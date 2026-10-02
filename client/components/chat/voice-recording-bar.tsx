"use client";

import { useEffect } from "react";
import { CheckIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { VoiceWaveform } from "@/components/chat/voice-waveform";
import { recordingWarning } from "@/lib/audio";

interface VoiceRecordingBarProps {
  elapsedSeconds: number;
  stream: MediaStream | null;
  onCancel: () => void;
  onConfirm: () => void;
}

export function VoiceRecordingBar({
  elapsedSeconds,
  stream,
  onCancel,
  onConfirm,
}: VoiceRecordingBarProps) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing) return;
      if (event.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);

  return (
    <div className="flex h-12 items-center px-1">
      <span className="sr-only" aria-live="polite">
        録音中
      </span>
      <span className="mr-3 h-2.5 w-2.5 shrink-0 rounded-full bg-destructive motion-safe:animate-pulse" />
      <VoiceWaveform stream={stream} />
      <span
        aria-live="polite"
        className="ml-3 shrink-0 text-xs tabular-nums text-destructive empty:ml-0"
      >
        {recordingWarning(elapsedSeconds)}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="録音を取り消す"
        onClick={onCancel}
        className="ml-3 h-8 w-8 shrink-0 rounded-full"
      >
        <XIcon className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        size="icon"
        aria-label="録音を確定"
        onClick={onConfirm}
        autoFocus
        className="ml-3 h-8 w-8 shrink-0 rounded-full"
      >
        <CheckIcon className="h-4 w-4" />
      </Button>
    </div>
  );
}
