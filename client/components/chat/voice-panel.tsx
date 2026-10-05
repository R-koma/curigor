"use client";

import { useEffect } from "react";
import { PauseIcon, PlayIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import {
  SPEECH_SPEEDS,
  type ConversationStatus,
  type SpeechSpeed,
  type TurnTimings,
} from "@/hooks/use-voice-conversation";
import type { TranscriptSegment } from "@/lib/stt/types";
import { cn } from "@/lib/utils";

const LABELS: Record<ConversationStatus, string> = {
  off: "",
  starting: "マイクを準備しています…",
  listening: "聞いています",
  thinking: "考え中…",
  speaking: "話しています",
  paused: "一時停止中",
};

const DOT: Record<ConversationStatus, string> = {
  off: "bg-muted-foreground",
  starting: "bg-muted-foreground",
  listening: "bg-success animate-pulse",
  thinking: "bg-warning",
  speaking: "bg-brand animate-pulse",
  paused: "bg-muted-foreground",
};

interface VoicePanelProps {
  status: ConversationStatus;
  segments: TranscriptSegment[];
  speed: SpeechSpeed;
  holdForReview: boolean;
  timings: TurnTimings | null;
  onSpeedChange: (speed: SpeechSpeed) => void;
  onPause: () => void;
  onResume: () => void;
  onSendNow: () => void;
  onDiscard: () => void;
  onEnd: () => void;
}

function seconds(from: number, to: number | null): string {
  return to === null ? "—" : `${((to - from) / 1000).toFixed(2)}s`;
}

export function formatTimings(timings: TurnTimings): string {
  return [
    `送信 ${seconds(timings.turnEnd, timings.sent)}`,
    `最初の文字 ${seconds(timings.turnEnd, timings.firstToken)}`,
    `最初の音 ${seconds(timings.turnEnd, timings.firstAudio)}`,
  ].join(" / ");
}

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable ||
      ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
  );
}

function isInside(target: EventTarget | null, selector: string): boolean {
  return target instanceof Element && target.closest(selector) !== null;
}

export function VoicePanel({
  status,
  segments,
  speed,
  holdForReview,
  timings,
  onSpeedChange,
  onPause,
  onResume,
  onSendNow,
  onDiscard,
  onEnd,
}: VoicePanelProps) {
  const paused = status === "paused";

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing || isTyping(event.target))
        return;
      if (
        isInside(event.target, "[role=dialog], [role=alertdialog], [role=menu]")
      )
        return;
      if (event.key === "Enter") {
        if (isInside(event.target, "button, a, [role=button]")) return;
        onSendNow();
      } else if (event.key === "Escape") (paused ? onResume : onPause)();
      else if (event.key === "Backspace") onDiscard();
      else return;
      event.preventDefault();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [paused, onDiscard, onPause, onResume, onSendNow]);

  return (
    <section
      aria-label="音声で対話中"
      className="rounded-2xl border border-border bg-card p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div
          role="status"
          className="flex items-center gap-2 text-sm font-medium text-foreground"
        >
          <span
            className={cn("size-2.5 rounded-full", DOT[status])}
            aria-hidden
          />
          {LABELS[status]}
        </div>
        <div className="flex items-center gap-1">
          <div
            className="flex rounded-full bg-muted p-0.5"
            role="group"
            aria-label="読み上げの速さ"
          >
            {SPEECH_SPEEDS.map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={speed === value}
                aria-label={`${value}倍`}
                onClick={() => onSpeedChange(value)}
                className={cn(
                  "cursor-pointer rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
                  speed === value
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {value}×
              </button>
            ))}
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={paused ? "再開" : "一時停止"}
            onClick={paused ? onResume : onPause}
            className="rounded-full"
          >
            {paused ? (
              <PlayIcon className="size-4" />
            ) : (
              <PauseIcon className="size-4" />
            )}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={onEnd}>
            テキストに戻る
          </Button>
        </div>
      </div>

      <p className="mt-3 min-h-12 text-prose leading-relaxed text-foreground">
        {segments.map((segment) =>
          segment.status === "done" ? (
            <span key={segment.id}>{segment.text}</span>
          ) : segment.status === "failed" ? (
            <span key={segment.id} className="text-destructive">
              （聞き取れませんでした）
            </span>
          ) : (
            <span
              key={segment.id}
              aria-label="文字起こし中"
              className="inline-flex align-middle"
            >
              <Spinner size="sm" />
            </span>
          ),
        )}
      </p>

      <p className="mt-2 text-2xs text-muted-foreground">
        話し終えたら「以上」と言うと送信します。Enter で送信、Esc
        で一時停止、Backspace で言い直し。イヤホン推奨。
      </p>
      {holdForReview && (
        <p className="mt-1 text-2xs text-caution-text">
          カードへの回答は「以上」で入力欄に入ります。確認してから送ってください。
        </p>
      )}
      {timings && process.env.NODE_ENV !== "production" && (
        <p className="mt-1 font-mono text-3xs text-muted-foreground">
          {formatTimings(timings)}
        </p>
      )}
    </section>
  );
}
