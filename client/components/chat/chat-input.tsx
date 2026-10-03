"use client";

import { useRef, useState } from "react";
import { ArrowUpIcon, ImageIcon, MicIcon, PlusIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { VoiceRecordingBar } from "@/components/chat/voice-recording-bar";
import { VoiceStatusRow } from "@/components/chat/voice-status-row";
import { useVoiceRecorder } from "@/hooks/use-voice-recorder";
import { appendTranscript, isRewrite } from "@/lib/audio";
import {
  ALLOWED_IMAGE_TYPES,
  MAX_IMAGES_PER_MESSAGE,
  prepareImage,
  validateImageFile,
  type PreparedImage,
} from "@/lib/image";
import { cn } from "@/lib/utils";

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
  ) => void;
  isLoading: boolean;
  placeholder?: string;
  allowImages?: boolean;
  sessionId?: string | null;
  allowVoice?: boolean;
  voiceMode?: boolean;
  autoSendVoice?: boolean;
  onVoiceStart?: () => void;
  restoredTranscript?: { text: string } | null;
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
  voiceMode = false,
  autoSendVoice = false,
  onVoiceStart,
  restoredTranscript = null,
}: ChatInputProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [attachedImages, setAttachedImages] = useState<AttachedImage[]>([]);
  const [attachError, setAttachError] = useState<string | null>(null);
  const [isPreparing, setIsPreparing] = useState(false);
  const [transcripts, setTranscripts] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const voice = useVoiceRecorder({
    sessionId,
    onTranscript: (text) => {
      if (autoSendVoice && !isLoading && attachedImages.length === 0) {
        onSend(
          appendTranscript(value, text).trim(),
          undefined,
          [...transcripts, text].join("\n"),
          true,
        );
        setTranscripts([]);
        return;
      }
      onChange(appendTranscript(value, text));
      setTranscripts((prev) => [...prev, text]);
    },
  });

  const [previousValue, setPreviousValue] = useState(value);
  if (value !== previousValue) {
    setPreviousValue(value);
    if (isRewrite(previousValue, value)) setTranscripts([]);
  }

  const [previousRestored, setPreviousRestored] = useState(restoredTranscript);
  if (restoredTranscript !== previousRestored) {
    setPreviousRestored(restoredTranscript);
    if (restoredTranscript) setTranscripts([restoredTranscript.text]);
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
      onSend(
        content,
        prepared.length > 0 ? prepared : undefined,
        rawTranscript,
      );
      attachedImages.forEach(({ preview }) => URL.revokeObjectURL(preview));
      setAttachedImages([]);
      setAttachError(null);
      setTranscripts([]);
    } catch (err) {
      setAttachError(
        err instanceof Error ? err.message : "画像の処理に失敗しました",
      );
    } finally {
      setIsPreparing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
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
      {attachError && (
        <p className="mb-2 text-xs text-destructive">{attachError}</p>
      )}

      {voice.error && (
        <div className="mb-2 flex items-center gap-2 text-xs text-destructive">
          <span>{voice.error}</span>
          {voice.canRetry && (
            <button
              type="button"
              onClick={() => void voice.retry()}
              className="cursor-pointer underline"
            >
              再試行
            </button>
          )}
        </div>
      )}

      {attachedImages.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {attachedImages.map(({ file, preview }, i) => (
            <div key={i} className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={preview}
                alt={file.name}
                className="h-16 w-16 rounded-lg object-cover border"
              />
              <button
                type="button"
                onClick={() => removeImage(i)}
                className="absolute -right-1.5 -top-1.5 flex h-4 w-4 cursor-pointer items-center justify-center rounded-full bg-foreground text-background"
              >
                <XIcon className="h-2.5 w-2.5" />
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
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-full"
                  onClick={() => setShowMenu((prev) => !prev)}
                >
                  <PlusIcon className="h-4 w-4" />
                </Button>

                {showMenu && (
                  <>
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setShowMenu(false)}
                    />
                    <div className="absolute bottom-full left-0 z-20 mb-2 w-52 rounded-xl border bg-popover shadow-md">
                      <button
                        type="button"
                        onClick={handleFileClick}
                        className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-sm hover:bg-accent cursor-pointer"
                      >
                        <ImageIcon className="h-4 w-4 text-muted-foreground" />
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
              {allowVoice && (
                <Button
                  type="button"
                  variant={voiceMode ? "default" : "ghost"}
                  size="icon"
                  aria-label="音声で入力"
                  onClick={() => {
                    onVoiceStart?.();
                    void voice.start();
                  }}
                  disabled={voice.status !== "idle"}
                  className={cn(
                    "rounded-full",
                    voiceMode
                      ? "h-12 w-12 sm:h-10 sm:w-10"
                      : "h-10 w-10 sm:h-8 sm:w-8",
                  )}
                >
                  <MicIcon className="h-4 w-4" />
                </Button>
              )}

              {hasContent ? (
                <Button
                  type="button"
                  size="icon"
                  aria-label="送信"
                  onClick={handleSend}
                  disabled={isLoading || isPreparing || voice.status !== "idle"}
                  className="h-8 w-8 rounded-full"
                >
                  <ArrowUpIcon className="h-4 w-4" />
                </Button>
              ) : (
                !allowVoice && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    disabled
                    className="h-8 w-8 rounded-full"
                  >
                    <MicIcon className="h-4 w-4" />
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
