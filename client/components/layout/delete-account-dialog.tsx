"use client";

import { useState } from "react";

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
import { Spinner } from "@/components/ui/spinner";
import { useAccountActions } from "@/hooks/use-account-actions";

interface DeleteAccountDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteAccountDialog({
  open,
  onOpenChange,
}: DeleteAccountDialogProps) {
  const { deleteAccount } = useAccountActions();
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async (event: React.MouseEvent) => {
    event.preventDefault();
    setDeleting(true);
    const deleted = await deleteAccount();
    setDeleting(false);
    if (!deleted) onOpenChange(false);
  };

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (!deleting) onOpenChange(next);
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>アカウントを削除しますか？</AlertDialogTitle>
          <AlertDialogDescription>
            アカウントと、ノート・まとめノート・学習メモ・対話の履歴・画像がすべて削除されます。元に戻せません
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={deleting}>キャンセル</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={deleting}
            onClick={(event) => void handleDelete(event)}
          >
            {deleting && <Spinner />}
            削除する
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
