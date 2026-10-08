"use client";

import { PencilIcon } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TooltipLabel } from "@/components/ui/tooltip";
import { TOPIC_MAX_LENGTH } from "@/lib/intake";

function normalized(topic: string): string {
  return topic.normalize("NFKC").trim().toLowerCase();
}

export function NavbarTopic({
  topic,
  onEdit,
}: {
  topic: string;
  onEdit?: (topic: string) => boolean;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [value, setValue] = useState(topic);
  const [isConfirming, setIsConfirming] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const next = value.trim();
  const canSave = next !== "" && normalized(next) !== normalized(topic);

  useEffect(() => {
    if (!isEditing) return;
    inputRef.current?.focus();
    inputRef.current?.select();
  }, [isEditing]);

  if (!onEdit && isEditing) setIsEditing(false);

  if (!onEdit || !isEditing) {
    return (
      <div className="flex min-w-0 items-center gap-1">
        <h1 className="max-w-xs truncate text-sm font-semibold">{topic}</h1>
        {onEdit && (
          <TooltipLabel label="トピックを編集">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="トピックを編集"
              onClick={() => {
                setValue(topic);
                setIsEditing(true);
              }}
            >
              <PencilIcon aria-hidden className="size-3.5" />
            </Button>
          </TooltipLabel>
        )}
      </div>
    );
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (canSave) setIsConfirming(true);
  };

  const apply = () => {
    if (onEdit(next)) {
      setIsEditing(false);
    } else {
      toast.error("接続が切れています。もう一度お試しください");
    }
  };

  return (
    <form onSubmit={submit} className="flex min-w-0 items-center gap-2">
      <Input
        ref={inputRef}
        aria-label="学習トピック"
        value={value}
        maxLength={TOPIC_MAX_LENGTH}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setIsEditing(false);
        }}
        className="min-w-0 flex-1"
      />
      <Button type="submit" size="sm" disabled={!canSave} className="shrink-0">
        保存
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="shrink-0"
        onClick={() => setIsEditing(false)}
      >
        キャンセル
      </Button>
      <AlertDialog open={isConfirming} onOpenChange={setIsConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>トピックを変更しますか？</AlertDialogTitle>
            <AlertDialogDescription>
              「{topic}」から「{next}
              」に変更します。深さの地図を新しいトピックで作り直し、これまでの到達度はリセットされます。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>キャンセル</AlertDialogCancel>
            <AlertDialogAction onClick={apply}>変更する</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </form>
  );
}
