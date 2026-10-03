"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LibraryIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  assignNoteCollection,
  dismissCollectionSuggestion,
  listCollections,
  targetForName,
  type CollectionSummary,
  type CollectionTarget,
} from "@/lib/collections";

interface NoteCollectionPickerProps {
  noteId: string;
  collectionId: string | null;
  suggestedCollection: string | null;
}

export function NoteCollectionPicker({
  noteId,
  collectionId,
  suggestedCollection,
}: NoteCollectionPickerProps) {
  const router = useRouter();
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [isPicking, setIsPicking] = useState(false);
  const [newName, setNewName] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    listCollections()
      .then(setCollections)
      .catch(() => setCollections([]));
  }, []);

  const run = async (action: () => Promise<void>) => {
    setIsSaving(true);
    try {
      await action();
      setIsPicking(false);
      setNewName("");
      router.refresh();
    } catch {
      toast.error("テーマの更新に失敗しました");
    } finally {
      setIsSaving(false);
    }
  };

  const assign = (target: CollectionTarget) =>
    run(() => assignNoteCollection(noteId, target));

  const current = collections.find((c) => c.id === collectionId);

  if (isPicking) {
    return (
      <div className="mb-8 space-y-3 rounded-xl border bg-card p-4">
        <p className="text-sm font-medium">テーマを選ぶ</p>
        <div className="flex flex-wrap gap-2">
          {collections
            .filter((c) => c.id !== collectionId)
            .map((c) => (
              <Button
                key={c.id}
                variant="outline"
                size="sm"
                disabled={isSaving}
                onClick={() => assign({ collectionId: c.id })}
              >
                {c.name}
              </Button>
            ))}
        </div>
        <div className="flex items-center gap-2">
          <Input
            aria-label="新しいテーマ名"
            placeholder="新しいテーマ名"
            value={newName}
            maxLength={100}
            onChange={(e) => setNewName(e.target.value)}
          />
          <Button
            size="sm"
            disabled={isSaving || !newName.trim()}
            onClick={() => assign({ newName: newName.trim() })}
          >
            作成して入れる
          </Button>
        </div>
        <div className="flex gap-2">
          {collectionId && (
            <Button
              variant="ghost"
              size="sm"
              disabled={isSaving}
              onClick={() => assign(null)}
            >
              テーマから外す
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={() => setIsPicking(false)}>
            キャンセル
          </Button>
        </div>
      </div>
    );
  }

  if (collectionId) {
    return (
      <div className="mb-8 flex items-center gap-2 text-sm">
        <LibraryIcon className="h-4 w-4 text-muted-foreground" />
        <span className="text-muted-foreground">テーマ:</span>
        <Link
          href={`/collections/${collectionId}`}
          className="font-medium hover:underline"
        >
          {current?.name ?? "テーマ"}
        </Link>
        <Button variant="ghost" size="sm" onClick={() => setIsPicking(true)}>
          テーマを変更
        </Button>
      </div>
    );
  }

  if (suggestedCollection) {
    return (
      <div className="mb-8 flex flex-wrap items-center gap-2 rounded-xl border border-primary/30 bg-primary/5 p-4 text-sm">
        <LibraryIcon className="h-4 w-4 text-primary" />
        <span className="mr-2">「{suggestedCollection}」にまとめますか？</span>
        <Button
          size="sm"
          disabled={isSaving}
          onClick={() =>
            assign(targetForName(suggestedCollection, collections))
          }
        >
          入れる
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={isSaving}
          onClick={() => setIsPicking(true)}
        >
          別のテーマを選ぶ
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={isSaving}
          onClick={() => run(() => dismissCollectionSuggestion(noteId))}
        >
          入れない
        </Button>
      </div>
    );
  }

  return (
    <div className="mb-8">
      <Button variant="ghost" size="sm" onClick={() => setIsPicking(true)}>
        <LibraryIcon className="h-4 w-4" />
        テーマに入れる
      </Button>
    </div>
  );
}
