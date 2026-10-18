"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { EllipsisIcon, PencilIcon, Trash2Icon } from "lucide-react";
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

export function StudyMemoActionsMenu({
  memoId,
  topic,
}: {
  memoId: string;
  topic: string;
}) {
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const menuFocusReturn = useMenuFocusReturn();

  async function handleDelete() {
    setDeleting(true);
    try {
      await fetchAPI(`/api/study-memos/${memoId}`, { method: "DELETE" });
      toast.success("学習メモを削除しました");
      router.replace("/study-memos");
      router.refresh();
    } catch {
      toast.error("学習メモを削除できませんでした。もう一度お試しください");
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
            <Link href={`/study-memos/${memoId}?edit=1`}>
              <PencilIcon className="size-4" />
              編集
            </Link>
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
            <AlertDialogTitle>学習メモを削除しますか？</AlertDialogTitle>
            <AlertDialogDescription>
              「{topic}
              」を削除します。元に戻せません。この学習メモから説明して作ったノートは残ります。
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
