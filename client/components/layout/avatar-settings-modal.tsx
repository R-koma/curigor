"use client";

import { Spinner } from "@/components/ui/spinner";
import { useRef, useState } from "react";
import { CameraIcon, Trash2Icon } from "lucide-react";
import { useErrorToast } from "@/hooks/use-error-toast";
import { authClient } from "@/lib/auth-client";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface AvatarSettingsModalProps {
  open: boolean;
  onClose: () => void;
  currentImage: string | null | undefined;
  userName: string;
  onImageUpdate: (url: string | null) => void;
}

export function AvatarSettingsModal({
  open,
  onClose,
  currentImage,
  userName,
  onImageUpdate,
}: AvatarSettingsModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useErrorToast(error);

  const displayImage = previewUrl ?? currentImage;
  const isBusy = isUploading || isRemoving;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Revoke previous object URL to prevent memory leak
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }

    setError(null);
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleSave = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const res = await fetch("/api/upload-avatar", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const data = (await res.json()) as { error?: string };
        throw new Error(
          data.error ??
            "写真をアップロードできませんでした。もう一度お試しください",
        );
      }

      const data = (await res.json()) as { url: string };
      await authClient.updateUser({ image: data.url });
      onImageUpdate(data.url);
      handleClose();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "写真を更新できませんでした。もう一度お試しください",
      );
    } finally {
      setIsUploading(false);
    }
  };

  const handleRemove = async () => {
    setIsRemoving(true);
    setError(null);

    try {
      await authClient.updateUser({ image: "" });
      onImageUpdate(null);
      handleClose();
    } catch {
      setError("写真を削除できませんでした。もう一度お試しください");
    } finally {
      setIsRemoving(false);
    }
  };

  const handleClose = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setSelectedFile(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleClose()}>
      <DialogContent className="max-w-xs p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-6 pb-0">
          <DialogTitle className="text-center text-base">
            プロフィール写真
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col items-center gap-4 px-6 py-6">
          <button
            type="button"
            onClick={() => !isBusy && fileInputRef.current?.click()}
            disabled={isBusy}
            className="group relative rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none"
            aria-label="写真を選択"
          >
            <Avatar className="size-28">
              <AvatarImage src={displayImage ?? undefined} />
              <AvatarFallback className="text-4xl font-light">
                {userName?.charAt(0).toUpperCase() ?? "U"}
              </AvatarFallback>
            </Avatar>
            <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/40 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
              <CameraIcon className="size-7 text-white" />
            </div>
          </button>

          <p className="text-xs text-muted-foreground">
            クリックして写真を変更
          </p>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>

        <DialogFooter className="flex-row items-center border-t px-4 py-3 gap-2">
          {currentImage && !previewUrl && (
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 text-destructive hover:text-destructive hover:bg-destructive/10 mr-auto"
              onClick={handleRemove}
              disabled={isBusy}
            >
              <Trash2Icon className="size-3.5" />
              削除
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClose}
            disabled={isBusy}
            className={currentImage && !previewUrl ? "" : "mr-auto sm:mr-0"}
          >
            キャンセル
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!selectedFile || isBusy}
            className="min-w-16"
          >
            {isUploading ? <Spinner size="sm" /> : "保存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
