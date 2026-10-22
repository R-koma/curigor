"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from "react";
import {
  ArrowUpIcon,
  KeyboardIcon,
  MicIcon,
  MicOffIcon,
  RotateCcwIcon,
  SettingsIcon,
  SquareIcon,
  XIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Tooltip,
  TooltipContent,
  TooltipLabel,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DEFAULT_SPEECH_SPEED,
  type ConversationStatus,
  type SpeechSpeed,
} from "@/hooks/use-voice-conversation";
import { levelIntervalMs } from "@/lib/audio-levels";
import { CARET_SKIP_ATTR, caretPointAt, textOffsetWithin } from "@/lib/caret";
import { closeSegments } from "@/lib/end-of-turn";
import type { TranscriptSegment } from "@/lib/stt/types";
import { useCoarsePointer } from "@/hooks/use-coarse-pointer";
import { cn } from "@/lib/utils";
import { AiNotice } from "@/components/chat/ai-notice";

const LABELS: Record<ConversationStatus, string> = {
  off: "",
  starting: "マイクを準備しています…",
  listening: "聞いています",
  thinking: "考え中…",
  speaking: "AI が話しています",
  paused: "一時停止中",
};

const ORB_TONE: Record<ConversationStatus, string> = {
  off: "bg-muted text-muted-foreground",
  starting: "bg-muted text-muted-foreground",
  listening: "bg-brand text-brand-foreground",
  thinking: "bg-brand-soft text-brand-text",
  speaking: "bg-brand-soft text-brand-text",
  paused: "bg-muted text-muted-foreground",
};

const ICON_BUTTON = "size-11 rounded-full pointer-fine:size-8";

const HINT_SEEN_KEY = "voice-hint-seen";
const SPEAKING_LINGER_MS = 600;

const SPEED_OPTIONS = [
  { value: 1, label: "ゆっくり" },
  { value: DEFAULT_SPEECH_SPEED, label: "標準" },
  { value: 1.5, label: "速く" },
] as const satisfies readonly { value: SpeechSpeed; label: string }[];

const SHORTCUTS = [
  { keys: "「以上」と言う", action: "送信", keyboard: false },
  { keys: "Enter", action: "今すぐ送信", keyboard: true },
  { keys: "Esc", action: "一時停止・再開", keyboard: true },
  { keys: "Backspace", action: "言い直し", keyboard: true },
  { keys: "話した内容を押す", action: "編集", keyboard: false },
  { keys: "編集中に中央のボタン", action: "話を続ける", keyboard: false },
] as const;

const LEVEL_GAIN = 4;

type SubscribeLevel = (listener: (level: number) => void) => () => void;

interface VoicePanelProps {
  status: ConversationStatus;
  segments: TranscriptSegment[];
  editedPrefix: string | null;
  speed: SpeechSpeed;
  noInterrupt: boolean;
  holdForReview: boolean;
  subscribeLevel?: SubscribeLevel;
  onSpeedChange: (speed: SpeechSpeed) => void;
  onNoInterruptChange: (noInterrupt: boolean) => void;
  onStopSpeech: () => void;
  onPause: () => void;
  onResume: () => void;
  onSendNow: () => void;
  onDiscard: () => void;
  onEnd: () => void;
  onBeginEdit: () => Promise<string | null>;
  onSubmitEdit: (text: string) => Promise<boolean>;
  onCancelEdit: () => void;
  onContinueEdit: (text: string) => Promise<void>;
}

function readHintSeen(): boolean {
  try {
    return localStorage.getItem(HINT_SEEN_KEY) === "1";
  } catch {
    return false;
  }
}

function writeHintSeen() {
  try {
    localStorage.setItem(HINT_SEEN_KEY, "1");
  } catch {
    return;
  }
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

const CARET_SKIP = { [CARET_SKIP_ATTR]: "" };

function clickedOffset(event: MouseEvent<HTMLElement>): number | null {
  if (event.detail === 0) return null;
  const point = caretPointAt(event.clientX, event.clientY);
  return point
    ? textOffsetWithin(event.currentTarget, point.node, point.offset)
    : null;
}

function LevelRing({ subscribe }: { subscribe: SubscribeLevel }) {
  const [level, setLevel] = useState(0);

  useEffect(() => {
    let peak = 0;
    const unsubscribe = subscribe((value) => {
      peak = Math.max(peak, Math.min(1, value * LEVEL_GAIN));
    });
    const timer = window.setInterval(() => {
      setLevel(peak);
      peak = 0;
    }, levelIntervalMs());
    return () => {
      unsubscribe();
      window.clearInterval(timer);
    };
  }, [subscribe]);

  return (
    <span
      role="img"
      aria-label="音声の波形"
      className="pointer-events-none absolute inset-0 rounded-full bg-brand/30 transition-transform duration-100"
      style={{ transform: `scale(${1 + level * 0.5})` }}
    />
  );
}

function OrbIcon({
  status,
  editing,
}: {
  status: ConversationStatus;
  editing: boolean;
}) {
  if (status === "starting") return <Spinner size="lg" />;
  if (status === "listening" || editing)
    return <MicIcon className="relative size-6" />;
  if (status === "speaking")
    return <SquareIcon className="size-5 fill-current" />;
  if (status === "thinking")
    return (
      <span className="flex gap-1" aria-hidden>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-1.5 rounded-full bg-current motion-safe:animate-pulse"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </span>
    );
  return <MicOffIcon className="size-6" />;
}

export function VoicePanel({
  status,
  segments,
  editedPrefix,
  speed,
  noInterrupt,
  holdForReview,
  subscribeLevel,
  onSpeedChange,
  onNoInterruptChange,
  onStopSpeech,
  onPause,
  onResume,
  onSendNow,
  onDiscard,
  onEnd,
  onBeginEdit,
  onSubmitEdit,
  onCancelEdit,
  onContinueEdit,
}: VoicePanelProps) {
  const coarsePointer = useCoarsePointer();
  const paused = status === "paused";
  const [hintSeen, setHintSeen] = useState(readHintSeen);
  const hasTranscript = editedPrefix !== null || segments.length > 0;
  const [draft, setDraft] = useState<string | null>(null);
  const [caret, setCaret] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [beginning, setBeginning] = useState(false);
  const editHintId = useId();
  const editing = draft !== null;
  const draftRef = useRef<HTMLTextAreaElement>(null);
  const [previousStatus, setPreviousStatus] = useState(status);
  const [lingering, setLingering] = useState(false);
  if (previousStatus !== status) {
    setPreviousStatus(status);
    setLingering(previousStatus === "speaking" && status === "thinking");
  }
  // 読み上げは文と文の間で一瞬 thinking に戻るので、その間も停止の操作を保つ
  const orbStatus = lingering ? "speaking" : status;
  const orb = editing
    ? {
        label: "話を続ける",
        onClick: submitting ? undefined : () => void continueEdit(),
        key: "",
      }
    : orbStatus === "speaking"
      ? { label: "読み上げを停止", onClick: onStopSpeech, key: "" }
      : status === "starting"
        ? { label: "マイクを準備しています", onClick: undefined, key: "" }
        : paused
          ? { label: "再開", onClick: onResume, key: " (Esc)" }
          : { label: "一時停止", onClick: onPause, key: " (Esc)" };

  if (status === "thinking" && !hintSeen) setHintSeen(true);

  useEffect(() => {
    if (hintSeen) writeHintSeen();
  }, [hintSeen]);

  useEffect(() => {
    if (!lingering) return;
    const timer = window.setTimeout(
      () => setLingering(false),
      SPEAKING_LINGER_MS,
    );
    return () => window.clearTimeout(timer);
  }, [lingering]);

  useEffect(() => {
    if (!editing) return;
    const box = draftRef.current;
    if (!box) return;
    box.focus();
    const position = Math.min(caret ?? box.value.length, box.value.length);
    box.setSelectionRange(position, position);
  }, [caret, editing]);

  const beginEdit = async (offset: number | null) => {
    if (beginning) return;
    setBeginning(true);
    try {
      const text = await onBeginEdit();
      if (text) {
        setCaret(offset);
        setDraft(text);
      }
    } finally {
      setBeginning(false);
    }
  };

  const submitEdit = async () => {
    if (draft === null || submitting) return;
    setSubmitting(true);
    const sent = await onSubmitEdit(draft);
    setSubmitting(false);
    if (sent) setDraft(null);
  };

  const continueEdit = async () => {
    if (draft === null || submitting) return;
    setDraft(null);
    await onContinueEdit(draft);
  };

  const cancelEdit = () => {
    setDraft(null);
    setSubmitting(false);
    onCancelEdit();
  };

  const handleDraftKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.nativeEvent.isComposing) return;
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitEdit();
    } else if (event.key === "Escape") {
      event.preventDefault();
      cancelEdit();
    }
  };

  useEffect(() => {
    if (editing || beginning) return;
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
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
  }, [beginning, editing, paused, onDiscard, onPause, onResume, onSendNow]);

  return (
    <section
      aria-label="音声で対話中"
      className="rounded-2xl border border-border bg-card p-4"
    >
      <p role="status" className="sr-only">
        {LABELS[status]}
      </p>

      <div className="flex items-start gap-1">
        <div className="min-w-0 flex-1">
          {editing ? (
            <div>
              <Textarea
                ref={draftRef}
                aria-label="聞き取った内容"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={handleDraftKeyDown}
                className="min-h-12 resize-none text-prose leading-relaxed md:text-prose"
              />
              <div className="mt-2 flex items-center justify-end gap-1">
                <TooltipLabel
                  label={coarsePointer ? "編集をやめる" : "編集をやめる (Esc)"}
                >
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label="編集をやめる"
                    onClick={cancelEdit}
                    className={cn(ICON_BUTTON, "text-muted-foreground")}
                  >
                    <XIcon className="size-4" />
                  </Button>
                </TooltipLabel>
                <TooltipLabel
                  label={
                    submitting
                      ? "応答の終わりを待っています"
                      : (holdForReview ? "入力欄に入れる" : "送信") +
                        (coarsePointer ? "" : " (Enter)")
                  }
                >
                  <Button
                    type="button"
                    variant="brand"
                    size="icon"
                    aria-label="直した内容を送信"
                    onClick={() => void submitEdit()}
                    disabled={submitting || !draft.trim()}
                    className="size-11 rounded-full pointer-fine:size-9"
                  >
                    {submitting ? (
                      <Spinner size="sm" />
                    ) : (
                      <ArrowUpIcon className="size-4" />
                    )}
                  </Button>
                </TooltipLabel>
              </div>
            </div>
          ) : (
            <div className="flex min-h-12 items-start gap-2">
              {hasTranscript ? (
                <>
                  <TooltipLabel label="編集">
                    <button
                      type="button"
                      aria-describedby={editHintId}
                      aria-disabled={beginning}
                      onClick={(event) => void beginEdit(clickedOffset(event))}
                      className="-mx-1 min-w-0 flex-1 cursor-text rounded-md px-1 text-left text-prose leading-relaxed text-foreground underline decoration-muted-foreground/60 decoration-dotted underline-offset-4 transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
                    >
                      {editedPrefix !== null && <span>{editedPrefix}</span>}
                      {closeSegments(segments).map((segment) =>
                        segment.status === "done" ? (
                          <span key={segment.id}>{segment.text}</span>
                        ) : segment.status === "failed" ? (
                          <span
                            key={segment.id}
                            {...CARET_SKIP}
                            className="text-destructive"
                          >
                            （聞き取れませんでした）
                          </span>
                        ) : (
                          <span
                            key={segment.id}
                            {...CARET_SKIP}
                            aria-label="文字起こし中"
                            className="inline-flex align-middle"
                          >
                            <Spinner size="sm" />
                          </span>
                        ),
                      )}
                    </button>
                  </TooltipLabel>
                  <span id={editHintId} className="sr-only">
                    押すと編集できます
                  </span>
                </>
              ) : (
                <p className="min-w-0 flex-1 text-prose leading-relaxed text-foreground">
                  {status === "listening" && !hintSeen && (
                    <span className="text-muted-foreground">
                      話し終えたら「以上」で送信
                    </span>
                  )}
                  {status === "speaking" && noInterrupt && (
                    <span className="text-muted-foreground">
                      読み上げ中は聞き取りません
                    </span>
                  )}
                </p>
              )}
              {hasTranscript && !paused && (
                <div className="flex shrink-0 items-center gap-1">
                  <TooltipLabel
                    label={coarsePointer ? "言い直し" : "言い直し (Backspace)"}
                  >
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label="言い直す"
                      onClick={onDiscard}
                      className={cn(ICON_BUTTON, "text-muted-foreground")}
                    >
                      <RotateCcwIcon className="size-4" />
                    </Button>
                  </TooltipLabel>
                  <TooltipLabel
                    label={
                      (holdForReview ? "入力欄に入れる" : "送信") +
                      (coarsePointer ? "" : " (Enter)")
                    }
                  >
                    <Button
                      type="button"
                      variant="brand"
                      size="icon"
                      aria-label={holdForReview ? "入力欄に入れる" : "送信"}
                      onClick={onSendNow}
                      className="size-11 rounded-full pointer-fine:size-9"
                    >
                      <ArrowUpIcon className="size-4" />
                    </Button>
                  </TooltipLabel>
                </div>
              )}
            </div>
          )}
        </div>
        <Popover>
          <TooltipLabel label="設定とヒント">
            <PopoverTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="設定とヒント"
                className={cn(ICON_BUTTON, "text-muted-foreground")}
              >
                <SettingsIcon className="size-4" />
              </Button>
            </PopoverTrigger>
          </TooltipLabel>
          <PopoverContent align="end" className="w-64">
            <p className="mb-4 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
              イヤホンの利用がおすすめです（AI の声を拾わないため）
            </p>
            <p className="text-xs font-medium text-muted-foreground">
              読み上げの速さ
            </p>
            <div
              role="group"
              aria-label="読み上げの速さ"
              className="mt-2 grid grid-cols-3 gap-1 rounded-lg bg-muted p-1"
            >
              {SPEED_OPTIONS.map(({ value, label }) => {
                const pressed = speed === value;
                return (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={pressed}
                    onClick={() => onSpeedChange(value)}
                    className={cn(
                      "h-9 cursor-pointer rounded-md text-sm transition-colors focus-visible:outline-2 focus-visible:outline-ring pointer-fine:h-7",
                      pressed
                        ? "bg-background font-medium text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            <div className="mt-4 flex items-start justify-between gap-3">
              <div>
                <p id="voice-no-interrupt-label" className="text-sm">
                  読み上げ中は割り込まない
                </p>
                <p
                  id="voice-no-interrupt-description"
                  className="mt-0.5 text-2xs text-muted-foreground"
                >
                  読み上げ中に話した声は聞き取りません。騒がしい場所向け
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={noInterrupt}
                aria-labelledby="voice-no-interrupt-label"
                aria-describedby="voice-no-interrupt-description"
                onClick={() => onNoInterruptChange(!noInterrupt)}
                className={cn(
                  "mt-0.5 inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full p-0.5 transition-colors focus-visible:outline-2 focus-visible:outline-ring",
                  noInterrupt ? "bg-brand" : "bg-input",
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "size-4 rounded-full bg-background shadow-sm transition-transform",
                    noInterrupt && "translate-x-4",
                  )}
                />
              </button>
            </div>
            <p className="mt-4 text-xs font-medium text-muted-foreground">
              操作
            </p>
            <dl className="mt-2 space-y-2 text-sm">
              {SHORTCUTS.filter(
                (shortcut) => !shortcut.keyboard || !coarsePointer,
              ).map(({ keys, action }) => (
                <div key={keys} className="flex justify-between gap-3">
                  <dt>
                    <kbd className="rounded-sm border border-border px-1.5 py-0.5 text-2xs">
                      {keys}
                    </kbd>
                  </dt>
                  <dd className="text-muted-foreground">{action}</dd>
                </div>
              ))}
            </dl>
          </PopoverContent>
        </Popover>
      </div>

      {holdForReview && (
        <p className="mt-1 text-2xs text-caution-text">
          「以上」で入力欄に入ります
        </p>
      )}
      <div className="mt-3 grid grid-cols-[1fr_auto_1fr] items-center">
        <span aria-hidden />
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label={orb.label}
              onClick={orb.onClick}
              aria-disabled={editing ? submitting : status === "starting"}
              className={cn(
                "relative flex size-16 shrink-0 cursor-pointer items-center justify-center rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring aria-disabled:cursor-default",
                ORB_TONE[orbStatus],
              )}
            >
              {status === "listening" && subscribeLevel && (
                <LevelRing subscribe={subscribeLevel} />
              )}
              <OrbIcon status={orbStatus} editing={editing} />
            </button>
          </TooltipTrigger>
          <TooltipContent
            onEscapeKeyDown={() => {
              if (!editing) (paused ? onResume : onPause)();
            }}
          >
            {orb.label + (coarsePointer ? "" : orb.key)}
          </TooltipContent>
        </Tooltip>
        <div className="justify-self-end">
          <TooltipLabel label="キーボードで入力">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="キーボードで入力"
              onClick={onEnd}
              className={cn(ICON_BUTTON, "text-muted-foreground")}
            >
              <KeyboardIcon className="size-5" />
            </Button>
          </TooltipLabel>
        </div>
      </div>
      <AiNotice voice className="mt-3" />
    </section>
  );
}
