"use client";

import { useRef, useState } from "react";
import { ArrowUpIcon, ImageIcon, MicIcon, PlusIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
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
  onSend: (content: string, images?: PreparedImage[]) => void;
  isLoading: boolean;
  placeholder?: string;
  allowImages?: boolean;
}

export function ChatInput({
  value,
  onChange,
  onSend,
  isLoading,
  placeholder = "入力...",
  allowImages = true,
}: ChatInputProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [attachedImages, setAttachedImages] = useState<AttachedImage[]>([]);
  const [attachError, setAttachError] = useState<string | null>(null);
  const [isPreparing, setIsPreparing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    if (isPreparing) return;
    if (!value.trim() && attachedImages.length === 0) return;

    const content = value.trim();
    try {
      setIsPreparing(true);
      const prepared: PreparedImage[] = await Promise.all(
        attachedImages.map(({ file }) => prepareImage(file)),
      );
      onSend(content, prepared.length > 0 ? prepared : undefined);
      attachedImages.forEach(({ preview }) => URL.revokeObjectURL(preview));
      setAttachedImages([]);
      setAttachError(null);
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

  return (
    <div className="rounded-2xl border bg-muted/50 p-3">
      {attachError && (
        <p className="mb-2 text-xs text-destructive">{attachError}</p>
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

      <Textarea
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        className="min-h-10 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0 dark:bg-transparent"
      />

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

        <div className="flex items-center">
          {hasContent ? (
            <Button
              type="button"
              size="icon"
              onClick={handleSend}
              disabled={isLoading || isPreparing}
              className="h-8 w-8 rounded-full"
            >
              <ArrowUpIcon className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled
              className="h-8 w-8 rounded-full"
            >
              <MicIcon className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
