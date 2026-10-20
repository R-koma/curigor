"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  ArrowUpIcon,
  AudioLinesIcon,
  CodeIcon,
  ImageIcon,
  MicIcon,
  PaperclipIcon,
  PlusIcon,
  RotateCcwIcon,
  SigmaIcon,
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
import { ComposePreview } from "@/components/chat/compose-preview";
import { InsertPanel, type InsertKind } from "@/components/chat/insert-panel";
import { VoiceRecordingBar } from "@/components/chat/voice-recording-bar";
import { VoiceStatusRow } from "@/components/chat/voice-status-row";
import { SEND_FAILED_MESSAGE } from "@/hooks/use-chat-websocket";
import { useErrorToast } from "@/hooks/use-error-toast";
import { useCoarsePointer } from "@/hooks/use-coarse-pointer";
import { useVoiceRecorder } from "@/hooks/use-voice-recorder";
import {
  appendTranscript,
  isRewrite,
  topicTranscriptionPrompt,
} from "@/lib/audio";
import {
  ALLOWED_IMAGE_TYPES,
  isAllowedImageType,
  MAX_IMAGES_PER_MESSAGE,
  prepareImage,
  validateImageFile,
  type PreparedImage,
} from "@/lib/image";
import { codePasteEdit } from "@/lib/code-paste";
import { isMessageTooLong, MESSAGE_TOO_LONG } from "@/lib/message-length";
import { attachmentText, MAX_TEXT_FILES, readTextFile } from "@/lib/text-file";
import { cn } from "@/lib/utils";
import { AiNotice } from "@/components/chat/ai-notice";
import {
  applyEdit,
  findMathAt,
  insertBlock,
  insertCodeBlock,
  insertMath,
  locateMath,
  replaceMath,
  type MathSpan,
  type TextEdit,
  type TextSelection,
} from "@/lib/compose-insert";

interface AttachedImage {
  file: File;
  preview: string; // object URL
}

interface OpenPanel {
  kind: InsertKind;
  math: MathSpan | null;
}

// Office 系のアプリは文字のコピーに、選択範囲を描いた画像のファイルも添える
function isRichTextCopy(data: DataTransfer, files: File[]): boolean {
  const types = Array.from(data.types ?? []);
  return (
    files.every((file) => isAllowedImageType(file.type)) &&
    (types.includes("text/html") || types.includes("text/rtf")) &&
    data.getData("text/plain").trim() !== ""
  );
}

const MENU_ITEM_CLASS =
  "flex w-full cursor-pointer items-center gap-2 rounded-xl px-3 py-2.5 text-sm hover:bg-accent";

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
  allowRichInput?: boolean;
  sessionId?: string | null;
  transcriptionTopic?: string | null;
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
  allowRichInput = false,
  sessionId = null,
  transcriptionTopic = null,
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
  const [tooLong, setTooLong] = useState(false);
  const lengthErrorId = useId();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textFileInputRef = useRef<HTMLInputElement>(null);
  const dragDepth = useRef(0);
  const [dragging, setDragging] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [panel, setPanel] = useState<OpenPanel | null>(null);
  const [pasteUndo, setPasteUndo] = useState<TextEdit | null>(null);
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useErrorToast(attachError);
  useErrorToast(sendError);

  const voice = useVoiceRecorder({
    sessionId,
    prompt: topicTranscriptionPrompt(transcriptionTopic),
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
    if (tooLong && !isMessageTooLong(value.trim())) setTooLong(false);
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

  const addImages = (files: File[]) => {
    setAttachedImages((prev) => {
      const next = [...prev];
      for (const file of files) {
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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files ?? []);
    e.target.value = "";
    setAttachError(null);
    addImages(selected);
  };

  const removeImage = (index: number) => {
    setAttachedImages((prev) => {
      const next = [...prev];
      const removed = next.splice(index, 1)[0];
      URL.revokeObjectURL(removed.preview);
      return next;
    });
  };

  const isRecording =
    allowVoice && (voice.status === "recording" || voice.status === "stopping");

  const coarsePointer = useCoarsePointer();

  const currentValue = () => textareaRef.current?.value ?? value;

  const currentSelection = (): TextSelection => {
    const textarea = textareaRef.current;
    return textarea
      ? { start: textarea.selectionStart, end: textarea.selectionEnd }
      : { start: value.length, end: value.length };
  };

  const applyTextEdit = (
    edit: TextEdit,
    { focus = true }: { focus?: boolean } = {},
  ) => {
    const textarea = textareaRef.current;
    if (textarea && focus) {
      textarea.focus();
      textarea.setSelectionRange(edit.start, edit.end);
      if (
        typeof document.execCommand === "function" &&
        document.execCommand("insertText", false, edit.text)
      ) {
        return;
      }
    }
    setPasteUndo(null);
    onChange(applyEdit(currentValue(), edit));
    if (!focus) return;
    const cursor = edit.start + edit.text.length;
    requestAnimationFrame(() =>
      textareaRef.current?.setSelectionRange(cursor, cursor),
    );
  };

  const dismissPanel = () => {
    setPanel(null);
    setKeyboardHeight(0);
  };

  const closePanel = () => {
    dismissPanel();
    textareaRef.current?.focus();
  };

  const openPanel = (kind: InsertKind) => {
    setShowMenu(false);
    const { start, end } = currentSelection();
    setPanel({
      kind,
      math: kind === "math" && start === end ? findMathAt(value, start) : null,
    });
  };

  const insertFormula = (latex: string) => {
    const math = panel?.math ? locateMath(value, panel.math) : null;
    const edit = math
      ? replaceMath(math, latex)
      : insertMath(value, currentSelection(), latex);
    applyTextEdit(edit);
    closePanel();
  };

  const insertCode = (code: string, fence: string) => {
    applyTextEdit(insertCodeBlock(value, currentSelection(), code, fence));
    closePanel();
  };

  const handleTextChange = (next: string) => {
    setPasteUndo(null);
    onChange(next);
  };

  const handlePaste = (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const files = Array.from(event.clipboardData.files ?? []);
    if (files.length > 0 && !isRichTextCopy(event.clipboardData, files)) {
      if (!allowRichInput || panel) return;
      event.preventDefault();
      void attachFiles(files);
      return;
    }
    const text = event.clipboardData.getData("text/plain");
    const edit = codePasteEdit(
      value,
      currentSelection(),
      text,
      event.clipboardData.getData("vscode-editor-data"),
    );
    if (!edit) return;
    event.preventDefault();
    applyTextEdit(edit);
    setPasteUndo({
      start: edit.start,
      end: edit.start + edit.text.length,
      text,
    });
  };

  const attachFiles = async (files: File[]) => {
    const images = files.filter((file) => isAllowedImageType(file.type));
    const others = files.filter((file) => !isAllowedImageType(file.type));
    const errors: string[] = [];
    setAttachError(null);
    if (images.length > 0) {
      if (allowImages) addImages(images);
      else errors.push("この欄には画像を添付できません");
    }
    if (others.length > MAX_TEXT_FILES) {
      errors.push(`ファイルは一度に${MAX_TEXT_FILES}つまでです`);
    }
    const results = await Promise.all(
      others.slice(0, MAX_TEXT_FILES).map(readTextFile),
    );
    const read = results.flatMap((result) => {
      if (result.ok) return [result.file];
      errors.push(result.error);
      return [];
    });
    const block = attachmentText(read);
    const edit = block
      ? insertBlock(currentValue(), currentSelection(), block)
      : null;
    if (edit && isMessageTooLong(applyEdit(currentValue(), edit))) {
      errors.unshift(`添付すると${MESSAGE_TOO_LONG}`);
    } else if (edit) {
      applyTextEdit(edit, { focus: !coarsePointer });
    }
    if (errors.length > 0) setAttachError(errors[0]);
  };

  useEffect(() => {
    if (!dragging) return;
    const reset = () => {
      dragDepth.current = 0;
      setDragging(false);
    };
    window.addEventListener("drop", reset);
    window.addEventListener("dragend", reset);
    return () => {
      window.removeEventListener("drop", reset);
      window.removeEventListener("dragend", reset);
    };
  }, [dragging]);

  const carriesFiles = (event: React.DragEvent) =>
    Array.from(event.dataTransfer.types).includes("Files");

  const acceptsDroppedFiles = (event: React.DragEvent) =>
    allowRichInput && !panel && !isRecording && carriesFiles(event);

  const undoPasteFence = () => {
    if (!pasteUndo) return;
    applyTextEdit(pasteUndo);
    setPasteUndo(null);
  };

  const handleSend = async () => {
    if (panel || isPreparing || voice.status !== "idle") return;
    if (!value.trim() && attachedImages.length === 0) return;

    const content = value.trim();
    if (isMessageTooLong(content)) {
      setTooLong(true);
      return;
    }
    const joinedTranscript = transcripts.join("\n");
    const rawTranscript =
      content && transcripts.length > 0 && !isMessageTooLong(joinedTranscript)
        ? joinedTranscript
        : undefined;
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
      setPasteUndo(null);
    } catch (err) {
      setAttachError(
        err instanceof Error ? err.message : "画像の処理に失敗しました",
      );
    } finally {
      setIsPreparing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (coarsePointer || panel) return;
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  const hasContent = value.trim() || attachedImages.length > 0;

  return (
    <div
      style={keyboardHeight > 0 ? { marginBottom: keyboardHeight } : undefined}
    >
      <div
        data-slot="chat-input"
        className={cn(
          "rounded-2xl border bg-muted/50 p-3",
          dragging && "ring-2 ring-brand",
        )}
        onClick={(event) => {
          const target = event.target as HTMLElement;
          if (
            target === event.currentTarget ||
            target.hasAttribute("data-chat-input-toolbar")
          ) {
            textareaRef.current?.focus();
          }
        }}
        onDragEnter={(event) => {
          if (!acceptsDroppedFiles(event)) return;
          dragDepth.current += 1;
          setDragging(true);
        }}
        onDragOver={(event) => {
          if (carriesFiles(event)) event.preventDefault();
        }}
        onDragLeave={() => {
          if (dragDepth.current === 0) return;
          dragDepth.current -= 1;
          if (dragDepth.current === 0) setDragging(false);
        }}
        onDrop={(event) => {
          dragDepth.current = 0;
          setDragging(false);
          if (carriesFiles(event)) event.preventDefault();
          if (!acceptsDroppedFiles(event)) return;
          void attachFiles(Array.from(event.dataTransfer.files));
        }}
      >
        {dragging && (
          <p role="status" className="mb-2 text-sm text-muted-foreground">
            ここにドロップしてファイルを添付
          </p>
        )}
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

        {!isRecording && panel && (
          <InsertPanel
            key={`${panel.kind}-${panel.math?.start ?? "new"}`}
            kind={panel.kind}
            initialLatex={panel.math?.latex}
            onInsertMath={insertFormula}
            onInsertCode={insertCode}
            onClose={closePanel}
            onKeyboardHeight={setKeyboardHeight}
          />
        )}
        {!isRecording && !panel && <ComposePreview value={value} />}

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
              ref={textareaRef}
              placeholder={placeholder}
              value={value}
              onChange={(e) => handleTextChange(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              aria-invalid={tooLong || undefined}
              aria-describedby={tooLong ? lengthErrorId : undefined}
              rows={1}
              className="min-h-10 max-h-60 resize-none pointer-coarse:max-h-32 overflow-y-auto border-0 bg-transparent shadow-none focus-visible:ring-0 dark:bg-transparent"
            />

            {tooLong && (
              <p id={lengthErrorId} className="px-2.5 text-xs text-destructive">
                {MESSAGE_TOO_LONG}。いまは
                {value.trim().length.toLocaleString("ja-JP")}字です
              </p>
            )}

            {pasteUndo && (
              <div
                role="status"
                className="flex items-center gap-1 px-2.5 text-xs text-muted-foreground"
              >
                <span>コードとして囲みました</span>
                <Button
                  type="button"
                  variant="link"
                  size="xs"
                  onClick={undoPasteFence}
                  className="pointer-coarse:h-11"
                >
                  元に戻す
                </Button>
              </div>
            )}

            {allowVoice && <VoiceStatusRow status={voice.status} />}

            <div
              data-chat-input-toolbar
              className="flex items-center justify-between pt-1"
            >
              {allowImages || allowRichInput ? (
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
                        aria-label="追加"
                        aria-haspopup="menu"
                        aria-expanded={showMenu}
                        className="size-8 rounded-full pointer-coarse:size-11"
                        onClick={() => setShowMenu((prev) => !prev)}
                      >
                        <PlusIcon className="size-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>追加</TooltipContent>
                  </Tooltip>

                  {showMenu && (
                    <>
                      <div
                        className="fixed inset-0 z-raised"
                        onClick={() => setShowMenu(false)}
                      />
                      <div className="absolute bottom-full left-0 z-menu mb-2 w-52 rounded-xl border bg-popover shadow-md">
                        {allowImages && (
                          <button
                            type="button"
                            onClick={handleFileClick}
                            className={MENU_ITEM_CLASS}
                          >
                            <ImageIcon className="size-4 text-muted-foreground" />
                            画像を追加
                          </button>
                        )}
                        {allowRichInput && (
                          <>
                            <button
                              type="button"
                              onClick={() => openPanel("math")}
                              className={MENU_ITEM_CLASS}
                            >
                              <SigmaIcon className="size-4 text-muted-foreground" />
                              数式を挿入
                            </button>
                            <button
                              type="button"
                              onClick={() => openPanel("code")}
                              className={MENU_ITEM_CLASS}
                            >
                              <CodeIcon className="size-4 text-muted-foreground" />
                              コードを挿入
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setShowMenu(false);
                                textFileInputRef.current?.click();
                              }}
                              disabled={panel !== null}
                              className={cn(
                                MENU_ITEM_CLASS,
                                "disabled:cursor-not-allowed disabled:opacity-50",
                              )}
                            >
                              <PaperclipIcon className="size-4 text-muted-foreground" />
                              ファイルを添付
                            </button>
                          </>
                        )}
                      </div>
                    </>
                  )}

                  {allowImages && (
                    <input
                      ref={fileInputRef}
                      type="file"
                      className="hidden"
                      multiple
                      accept={ALLOWED_IMAGE_TYPES.join(",")}
                      onChange={handleFileChange}
                    />
                  )}
                  {allowRichInput && (
                    <input
                      ref={textFileInputRef}
                      data-testid="text-file-input"
                      type="file"
                      className="hidden"
                      multiple
                      onChange={(event) => {
                        const files = Array.from(event.target.files ?? []);
                        event.target.value = "";
                        void attachFiles(files);
                      }}
                    />
                  )}
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
                      onClick={() => {
                        dismissPanel();
                        onStartConversation();
                      }}
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
                        dismissPanel();
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
                        isLoading ||
                        isPreparing ||
                        voice.status !== "idle" ||
                        panel !== null
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
      <AiNotice className="mt-2" />
    </div>
  );
}
