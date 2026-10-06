"use client";

import { useEffect } from "react";
import { PauseIcon, PlayIcon, RabbitIcon, TurtleIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DEFAULT_SPEECH_SPEED,
  type ConversationStatus,
  type SpeechSpeed,
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
  onSpeedChange: (speed: SpeechSpeed) => void;
  onPause: () => void;
  onResume: () => void;
  onSendNow: () => void;
  onDiscard: () => void;
  onEnd: () => void;
}

const SPEED_TOGGLES = [
  {
    value: 1,
    label: "ゆっくり読み上げる",
    hint: "AIの読み上げを遅くする",
    Icon: TurtleIcon,
  },
  {
    value: 1.5,
    label: "速く読み上げる",
    hint: "AIの読み上げを速くする",
    Icon: RabbitIcon,
  },
] as const satisfies readonly {
  value: SpeechSpeed;
  label: string;
  hint: string;
  Icon: typeof TurtleIcon;
}[];

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
            className="flex items-center"
            role="group"
            aria-label="読み上げの速さ"
          >
            {SPEED_TOGGLES.map(({ value, label, hint, Icon }) => {
              const pressed = speed === value;
              return (
                <Tooltip key={value}>
                  <TooltipTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-pressed={pressed}
                      aria-label={label}
                      onClick={() =>
                        onSpeedChange(pressed ? DEFAULT_SPEECH_SPEED : value)
                      }
                      className={cn(
                        "rounded-full",
                        pressed
                          ? "bg-muted text-foreground"
                          : "text-muted-foreground",
                      )}
                    >
                      <Icon className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent
                    onEscapeKeyDown={() => (paused ? onResume : onPause)()}
                  >
                    {pressed ? "標準の速さに戻す" : hint}
                  </TooltipContent>
                </Tooltip>
              );
            })}
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
    </section>
  );
}
