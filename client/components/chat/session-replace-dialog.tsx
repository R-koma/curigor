"use client";

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
import type { ActiveSession } from "@/lib/active-session";
import { SESSION_TYPE_DISPLAY } from "@/lib/status-display";

export function SessionReplaceDialog({
  session,
  onConfirm,
  onCancel,
}: {
  session: ActiveSession | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const label = session ? SESSION_TYPE_DISPLAY[session.session_type].label : "";
  const name = session?.topic ? `「${session.topic}」` : "セッション";

  return (
    <AlertDialog
      open={session !== null}
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            進行中のセッションを終了しますか？
          </AlertDialogTitle>
          <AlertDialogDescription>
            進行中の{name}（{label}）は終了し、続きから再開できなくなります。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>キャンセル</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>
            終了して始める
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
