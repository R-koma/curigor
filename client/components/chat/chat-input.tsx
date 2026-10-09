"use client";

import { useRef, useState } from "react";
import {
  ArrowUpIcon,
  AudioLinesIcon,
  ImageIcon,
  MicIcon,
  PlusIcon,
  RotateCcwIcon,
  XIcon,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipLabel,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { VoiceRecordingBar } from "@/components/chat/voice-recording-bar";
import { VoiceStatusRow } from "@/components/chat/voice-status-row";
import { SEND_FAILED_MESSAGE } from "@/hooks/use-chat-websocket";
import { useErrorToast } from "@/hooks/use-error-toast";
import { useCoarsePointer } from "@/hooks/use-coarse-pointer";
import { useVoiceRecorder } from "@/hooks/use-voice-recorder";
import { appendTranscript, isRewrite } from "@/lib/audio";
import {
  ALLOWED_IMAGE_TYPES,
  MAX_IMAGES_PER_MESSAGE,
  prepareImage,
  validateImageFile,
  type PreparedImage,
} from "@/lib/image";

interface AttachedImage {
  file: File;
  preview: string; // object URL
}

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (
    content: string,
    images?: PreparedImage[],
    rawTranscript?: string,
    autoSent?: boolean,
  ) => boolean | void;
  isLoading: boolean;
  placeholder?: string;
  allowImages?: boolean;
  sessionId?: string | null;
  allowVoice?: boolean;
  onVoiceStart?: () => void;
  onStartConversation?: () => void;
  restoredTranscript?: { text: string; autoSent?: boolean } | null;
}

export function ChatInput({
  value,
  onChange,
  onSend,
  isLoading,
  placeholder = "入力...",
  allowImages = true,
  sessionId = null,
  allowVoice = false,
  onVoiceStart,
  onStartConversation,
  restoredTranscript = null,
}: ChatInputProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [addTooltipOpen, setAddTooltipOpen] = useState(false);
  const [attachedImages, setAttachedImages] = useState<AttachedImage[]>([]);
  const [attachError, setAttachError] = useState<string | null>(null);
  const [isPreparing, setIsPreparing] = useState(false);
  const [transcripts, setTranscripts] = useState<string[]>(
    restoredTranscript ? [restoredTranscript.text] : [],
  );
  const [restoredAutoSent, setRestoredAutoSent] = useState(
    restoredTranscript?.autoSent === true,
  );
  const [sendError, setSendError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useErrorToast(attachError);
  useErrorToast(sendError);

  const voice = useVoiceRecorder({
    sessionId,
    onTranscript: (text) => {
      onChange(appendTranscript(value, text));
      setTranscripts((prev) => [...prev, text]);
    },
  });
  useErrorToast(
    voice.error,
    voice.canRetry
      ? {
          label: (
            <>
              <RotateCcwIcon className="size-4" aria-hidden />
              <span className="sr-only">再試行</span>
            </>
          ),
          onClick: () => void voice.retry(),
        }
      : undefined,
  );

  const [previousValue, setPreviousValue] = useState(value);
  if (value !== previousValue) {
    setPreviousValue(value);
    if (isRewrite(previousValue, value)) {
      setTranscripts([]);
      setRestoredAutoSent(false);
    }
  }

  const [previousRestored, setPreviousRestored] = useState(restoredTranscript);
  if (restoredTranscript !== previousRestored) {
    setPreviousRestored(restoredTranscript);
    if (restoredTranscript) {
      setTranscripts([restoredTranscript.text]);
      setRestoredAutoSent(restoredTranscript.autoSent === true);
    }
  }

  const handleFileClick = () => {
    setShowMenu(false);
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files ?? []);
    e.target.value = "";
    setAttachError(null);

    setAttachedImages((prev) => {
      const next = [...prev];
      for (const file of selected) {
        if (next.length >= MAX_IMAGES_PER_MESSAGE) {
          setAttachError(`画像は最大${MAX_IMAGES_PER_MESSAGE}枚までです`);
          break;
        }
        const error = validateImageFile(file);
        if (error) {
          setAttachError(error);
          continue;
        }
        next.push({ file, preview: URL.createObjectURL(file) });
      }
      return next;
    });
  };

  const removeImage = (index: number) => {
    setAttachedImages((prev) => {
      const next = [...prev];
      const removed = next.splice(index, 1)[0];
      URL.revokeObjectURL(removed.preview);
      return next;
    });
  };

  const coarsePointer = useCoarsePointer();

  const handleSend = async () => {
    if (isPreparing || voice.status !== "idle") return;
    if (!value.trim() && attachedImages.length === 0) return;

    const content = value.trim();
    const rawTranscript =
      content && transcripts.length > 0 ? transcripts.join("\n") : undefined;
    try {
      setIsPreparing(true);
      const prepared: PreparedImage[] = await Promise.all(
        attachedImages.map(({ file }) => prepareImage(file)),
      );
      const images = prepared.length > 0 ? prepared : undefined;
      const sent =
        rawTranscript && restoredAutoSent
          ? onSend(content, images, rawTranscript, true)
          : onSend(content, images, rawTranscript);
      if (sent === false) {
        setSendError(SEND_FAILED_MESSAGE);
        return;
      }
      setSendError(null);
      attachedImages.forEach(({ preview }) => URL.revokeObjectURL(preview));
      setAttachedImages([]);
      setAttachError(null);
      setTranscripts([]);
      setRestoredAutoSent(false);
    } catch (err) {
      setAttachError(
        err instanceof Error ? err.message : "画像の処理に失敗しました",
      );
    } finally {
      setIsPreparing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (coarsePointer) return;
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  const hasContent = value.trim() || attachedImages.length > 0;
  const isRecording =
    allowVoice && (voice.status === "recording" || voice.status === "stopping");

  return (
    <div className="rounded-2xl border bg-muted/50 p-3">
      {attachedImages.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {attachedImages.map(({ file, preview }, i) => (
            <div key={i} className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={preview}
                alt={file.name}
                className="size-16 rounded-lg object-cover border"
              />
              <button
                type="button"
                onClick={() => removeImage(i)}
                className="absolute -right-1.5 -top-1.5 flex size-4 cursor-pointer items-center justify-center rounded-full bg-foreground text-background"
              >
                <XIcon className="size-2.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {isRecording ? (
        <VoiceRecordingBar
          elapsedSeconds={voice.elapsedSeconds}
          stream={voice.stream}
          busy={voice.status === "stopping"}
          onCancel={voice.cancel}
          onConfirm={voice.stop}
        />
      ) : (
        <>
          <Textarea
            placeholder={placeholder}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            className="min-h-10 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0 dark:bg-transparent"
          />

          {allowVoice && <VoiceStatusRow status={voice.status} />}

          <div className="flex items-center justify-between pt-1">
            {allowImages ? (
              <div className="relative">
                <Tooltip
                  open={addTooltipOpen && !showMenu}
                  onOpenChange={setAddTooltipOpen}
                >
                  <TooltipTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label="画像を追加"
                      aria-haspopup="menu"
                      aria-expanded={showMenu}
                      className="size-8 rounded-full pointer-coarse:size-11"
                      onClick={() => setShowMenu((prev) => !prev)}
                    >
                      <PlusIcon className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>画像を追加</TooltipContent>
                </Tooltip>

                {showMenu && (
                  <>
                    <div
                      className="fixed inset-0 z-raised"
                      onClick={() => setShowMenu(false)}
                    />
                    <div className="absolute bottom-full left-0 z-menu mb-2 w-52 rounded-xl border bg-popover shadow-md">
                      <button
                        type="button"
                        onClick={handleFileClick}
                        className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-sm hover:bg-accent cursor-pointer"
                      >
                        <ImageIcon className="size-4 text-muted-foreground" />
                        画像を追加
                      </button>
                    </div>
                  </>
                )}

                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  multiple
                  accept={ALLOWED_IMAGE_TYPES.join(",")}
                  onChange={handleFileChange}
                />
              </div>
            ) : (
              <div />
            )}

            <div className="flex items-center gap-1">
              {allowVoice && onStartConversation && !hasContent && (
                <TooltipLabel label="声で話す">
                  <Button
                    type="button"
                    variant="brand"
                    size="icon"
                    aria-label="声で話す"
                    onClick={onStartConversation}
                    disabled={voice.status !== "idle"}
                    className="size-8 rounded-full pointer-coarse:size-11"
                  >
                    <AudioLinesIcon className="size-4" />
                  </Button>
                </TooltipLabel>
              )}

              {allowVoice && (
                <TooltipLabel label="音声で入力">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label="音声で入力"
                    onClick={() => {
                      onVoiceStart?.();
                      void voice.start();
                    }}
                    disabled={voice.status !== "idle"}
                    className="size-8 rounded-full pointer-coarse:size-11"
                  >
                    <MicIcon className="size-4" />
                  </Button>
                </TooltipLabel>
              )}

              {hasContent ? (
                <TooltipLabel label="送信">
                  <Button
                    type="button"
                    size="icon"
                    aria-label="送信"
                    onClick={handleSend}
                    disabled={
                      isLoading || isPreparing || voice.status !== "idle"
                    }
                    className="size-8 rounded-full pointer-coarse:size-11"
                  >
                    <ArrowUpIcon className="size-4" />
                  </Button>
                </TooltipLabel>
              ) : (
                !allowVoice && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    disabled
                    aria-hidden
                    className="size-8 rounded-full pointer-coarse:size-11"
                  >
                    <MicIcon className="size-4" />
                  </Button>
                )
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
