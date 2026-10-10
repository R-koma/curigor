"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CopyIcon, EllipsisIcon, PencilIcon, Trash2Icon } from "lucide-react";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { TooltipLabel } from "@/components/ui/tooltip";
import { useMenuFocusReturn } from "@/hooks/use-menu-focus-return";
import { fetchAPI } from "@/lib/api";
import { buildNoteMarkdown } from "@/lib/note-markdown";

interface NoteActionsMenuProps {
  noteId: string;
  topic: string;
  summary: string;
  content: string;
}

export function NoteActionsMenu({
  noteId,
  topic,
  summary,
  content,
}: NoteActionsMenuProps) {
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const menuFocusReturn = useMenuFocusReturn();

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(
        buildNoteMarkdown({ topic, summary, content }),
      );
      toast.success("Markdown をコピーしました");
    } catch {
      toast.error("コピーできませんでした。このブラウザでは利用できません");
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await fetchAPI(`/api/notes/${noteId}`, { method: "DELETE" });
      toast.success("ノートを削除しました");
      router.replace("/notes");
    } catch {
      toast.error("ノートを削除できませんでした。もう一度お試しください");
      setDeleting(false);
    }
  }

  return (
    <>
      <DropdownMenu>
        <TooltipLabel label="その他の操作">
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon-lg"
              aria-label="その他の操作"
              className="text-muted-foreground hover:bg-transparent hover:text-foreground aria-expanded:bg-transparent aria-expanded:text-foreground dark:hover:bg-transparent"
            >
              <EllipsisIcon className="size-4" />
            </Button>
          </DropdownMenuTrigger>
        </TooltipLabel>
        <DropdownMenuContent
          align="end"
          className="w-auto"
          {...menuFocusReturn}
        >
          <DropdownMenuItem asChild className="gap-2 px-3">
            <Link href={`/notes/${noteId}?edit=1`}>
              <PencilIcon className="size-4" />
              編集
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem className="gap-2 px-3" onSelect={handleCopy}>
            <CopyIcon className="size-4" />
            Markdown をコピー
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            variant="destructive"
            className="gap-2 px-3"
            onSelect={() => setConfirmOpen(true)}
          >
            <Trash2Icon className="size-4" />
            削除
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog
        open={confirmOpen}
        onOpenChange={(open) => !deleting && setConfirmOpen(open)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>ノートを削除しますか？</AlertDialogTitle>
            <AlertDialogDescription>
              「{topic}
              」を削除します。フィードバックと復習の予定も削除され、元に戻せません。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>
              キャンセル
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleting}
              onClick={(event) => {
                event.preventDefault();
                void handleDelete();
              }}
            >
              {deleting ? "削除中…" : "削除"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
