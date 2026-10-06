"use client";

import { useEffect, useState } from "react";
import { CheckIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { VoiceWaveform } from "@/components/chat/voice-waveform";
import { useAudioHistory } from "@/hooks/use-audio-history";
import { recordingWarning } from "@/lib/audio";
import {
  SILENCE_LEVEL,
  SILENCE_SECONDS,
  isSilentFor,
  levelIntervalMs,
} from "@/lib/audio-levels";

interface VoiceRecordingBarProps {
  elapsedSeconds: number;
  stream: MediaStream | null;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

const BUTTON_SIZE = "ml-3 size-10 shrink-0 rounded-full sm:h-8 sm:w-8";

export function VoiceRecordingBar({
  elapsedSeconds,
  stream,
  busy,
  onCancel,
  onConfirm,
}: VoiceRecordingBarProps) {
  const history = useAudioHistory(stream);
  const [heardVoice, setHeardVoice] = useState(false);
  if (!heardVoice && history.some((level) => level >= SILENCE_LEVEL)) {
    setHeardVoice(true);
  }
  const silent =
    !heardVoice && isSilentFor(history, SILENCE_SECONDS, levelIntervalMs());
  const message = silent
    ? "声が聞こえません。マイクを確認してください"
    : recordingWarning(elapsedSeconds);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (busy || event.defaultPrevented || event.isComposing) return;
      if (event.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [busy, onCancel]);

  return (
    <div
      data-testid="voice-recording-bar"
      className="flex min-h-[76px] items-center px-1 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-150"
    >
      <span className="sr-only" aria-live="polite">
        録音中
      </span>
      <span className="mr-3 size-2.5 shrink-0 rounded-full bg-destructive motion-safe:animate-pulse" />
      <VoiceWaveform history={history} />
      <span
        aria-live="polite"
        className="ml-3 min-w-0 text-xs tabular-nums text-destructive empty:ml-0"
      >
        {message}
      </span>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="録音を取り消す"
            onClick={onCancel}
            disabled={busy}
            className={BUTTON_SIZE}
          >
            <XIcon className="size-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent
          onEscapeKeyDown={() => {
            if (!busy) onCancel();
          }}
        >
          取り消し（Esc）
        </TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            size="icon"
            aria-label="録音を確定"
            onClick={onConfirm}
            disabled={busy}
            className={BUTTON_SIZE}
          >
            <CheckIcon className="size-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent
          onEscapeKeyDown={() => {
            if (!busy) onCancel();
          }}
        >
          確定して文字起こし
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
