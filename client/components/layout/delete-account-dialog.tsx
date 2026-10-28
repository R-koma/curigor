"use client";

import { useId, useState } from "react";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { useAccountActions } from "@/hooks/use-account-actions";

interface DeleteAccountDialogProps {
  email: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteAccountDialog({
  email,
  open,
  onOpenChange,
}: DeleteAccountDialogProps) {
  const { deleteAccount } = useAccountActions();
  const [deleting, setDeleting] = useState(false);
  const [typed, setTyped] = useState("");
  const inputId = useId();
  const confirmed = typed.trim().toLowerCase() === email.trim().toLowerCase();

  const handleOpenChange = (next: boolean) => {
    if (deleting) return;
    if (!next) setTyped("");
    onOpenChange(next);
  };

  const handleDelete = async (event: React.MouseEvent) => {
    event.preventDefault();
    if (!confirmed) return;
    setDeleting(true);
    const deleted = await deleteAccount();
    setDeleting(false);
    if (!deleted) handleOpenChange(false);
  };

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>アカウントを削除しますか？</AlertDialogTitle>
          <AlertDialogDescription>
            アカウントと、ノート・まとめノート・学習メモ・対話の履歴・画像がすべて削除されます。元に戻せません
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2">
          <Label htmlFor={inputId}>
            確認のため、メールアドレス（{email}）を入力してください
          </Label>
          <Input
            id={inputId}
            type="email"
            autoComplete="off"
            value={typed}
            disabled={deleting}
            onChange={(event) => setTyped(event.target.value)}
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={deleting}>キャンセル</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={!confirmed || deleting}
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
