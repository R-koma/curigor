"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CheckIcon, TagIcon, XIcon } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { TooltipLabel } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fetchAPI } from "@/lib/api";

interface NoteCategoryEditorProps {
  noteId: string;
  category: string | null;
}

export function NoteCategoryEditor({
  noteId,
  category,
}: NoteCategoryEditorProps) {
  const router = useRouter();
  const [isEditing, setIsEditing] = useState(false);
  const [value, setValue] = useState(category ?? "");
  const [isSaving, setIsSaving] = useState(false);

  const startEditing = () => {
    setValue(category ?? "");
    setIsEditing(true);
  };

  const handleSave = async () => {
    const trimmed = value.trim();
    if (!trimmed || trimmed === category) {
      setIsEditing(false);
      return;
    }
    setIsSaving(true);
    try {
      await fetchAPI(`/api/notes/${noteId}`, {
        method: "PATCH",
        body: JSON.stringify({ category: trimmed }),
      });
      setIsEditing(false);
      router.refresh();
    } catch {
      toast.error("カテゴリーを更新できませんでした。もう一度お試しください");
    } finally {
      setIsSaving(false);
    }
  };

  if (isEditing) {
    return (
      <div className="flex items-center gap-1.5">
        <Input
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSave();
            if (e.key === "Escape") setIsEditing(false);
          }}
          disabled={isSaving}
          placeholder="カテゴリー名"
          className="h-7 w-40 text-sm"
          aria-label="カテゴリー名"
        />
        <TooltipLabel label="保存">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-7"
            onClick={handleSave}
            disabled={isSaving}
            aria-label="保存"
          >
            <CheckIcon className="size-4" />
          </Button>
        </TooltipLabel>
        <TooltipLabel label="キャンセル">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-7"
            onClick={() => setIsEditing(false)}
            disabled={isSaving}
            aria-label="キャンセル"
          >
            <XIcon className="size-4" />
          </Button>
        </TooltipLabel>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={startEditing}
      className="cursor-pointer"
      aria-label="カテゴリーを編集"
    >
      {category ? (
        <Badge variant="outline" className="gap-1 font-normal">
          <TagIcon className="size-3" />
          {category}
        </Badge>
      ) : (
        <span className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground">
          <TagIcon className="size-3" />
          カテゴリーを追加
        </span>
      )}
    </button>
  );
}
