"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Markdown } from "@/components/ui/markdown";

export function NotePeekDialog({
  open,
  content,
  onClose,
}: {
  open: boolean;
  content: string;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="flex max-h-[85dvh] w-[calc(100%-2rem)] max-w-2xl flex-col">
        <DialogHeader>
          <DialogTitle>ノート</DialogTitle>
          <DialogDescription>
            読んだら閉じて、自分の言葉で説明してみましょう
          </DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <Markdown variant="article">{content}</Markdown>
        </div>
        <DialogFooter>
          <Button variant="brand" onClick={onClose}>
            閉じて説明する
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
