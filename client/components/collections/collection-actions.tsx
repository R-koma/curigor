"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { fetchAPI } from "@/lib/api";

export function CollectionActions({
  collectionId,
  name,
}: {
  collectionId: string;
  name: string;
}) {
  const router = useRouter();
  const [isRenaming, setIsRenaming] = useState(false);
  const [value, setValue] = useState(name);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);

  const rename = async () => {
    const trimmed = value.trim();
    if (!trimmed || trimmed === name) {
      setIsRenaming(false);
      return;
    }
    try {
      await fetchAPI(`/api/collections/${collectionId}`, {
        method: "PATCH",
        body: JSON.stringify({ name: trimmed }),
      });
      setIsRenaming(false);
      router.refresh();
    } catch (e) {
      toast.error(
        e instanceof Error && e.message.includes("409")
          ? "同じ名前のまとめノートがあります"
          : "名前の変更に失敗しました",
      );
    }
  };

  const remove = async () => {
    try {
      await fetchAPI(`/api/collections/${collectionId}`, { method: "DELETE" });
      router.push("/collections");
    } catch {
      toast.error("まとめノートの削除に失敗しました");
    }
  };

  return (
    <div className="flex items-center gap-2">
      {isRenaming ? (
        <>
          <Input
            aria-label="まとめノート名"
            value={value}
            maxLength={100}
            onChange={(e) => setValue(e.target.value)}
          />
          <Button size="sm" onClick={rename}>
            保存
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsRenaming(false)}
          >
            キャンセル
          </Button>
        </>
      ) : (
        <>
          <Button variant="ghost" size="sm" onClick={() => setIsRenaming(true)}>
            名前を変更
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsConfirmingDelete(true)}
          >
            まとめノートを削除
          </Button>
        </>
      )}
      <AlertDialog
        open={isConfirmingDelete}
        onOpenChange={setIsConfirmingDelete}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>まとめノートを削除しますか？</AlertDialogTitle>
            <AlertDialogDescription>
              「{name}
              」を削除します。ノートは削除されず、まとめノートから外れます。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>キャンセル</AlertDialogCancel>
            <AlertDialogAction onClick={remove}>削除する</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
