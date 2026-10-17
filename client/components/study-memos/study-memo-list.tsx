import Link from "next/link";
import { NotebookPenIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { StudyMemoSummary } from "@/lib/study-memos";

export function StudyMemoList({ memos }: { memos: StudyMemoSummary[] }) {
  if (memos.length === 0) {
    return (
      <EmptyState
        icon={NotebookPenIcon}
        title="学習メモはありません。"
        description="AI に教わるセッションを終えると、教わった内容がここに残ります。"
        action={
          <Button
            asChild
            variant="outline"
            size="sm"
            className="pointer-coarse:h-11 pointer-coarse:px-4"
          >
            <Link href="/learn?mode=explore">AI に教わる</Link>
          </Button>
        }
      />
    );
  }

  return (
    <ul className="space-y-3">
      {memos.map((memo) => (
        <li
          key={memo.id}
          className="flex items-center gap-3 rounded-xl border bg-card pr-4 transition-colors hover:bg-muted/60"
        >
          <Link
            href={`/study-memos/${memo.id}`}
            className="flex min-w-0 flex-1 flex-col gap-1 p-5"
          >
            <span className="truncate font-semibold">{memo.topic}</span>
            <span className="truncate text-sm text-muted-foreground">
              {new Date(memo.created_at).toLocaleDateString("ja-JP")}
              {memo.source && ` · ${memo.source}`}
            </span>
          </Link>
          {memo.handed_over ? (
            <Badge variant="success" className="shrink-0">
              説明済み
            </Badge>
          ) : (
            <Button
              asChild
              size="sm"
              variant="outline"
              className="shrink-0 pointer-coarse:h-11 pointer-coarse:px-4"
            >
              <Link href={`/learn?memo=${memo.id}`}>説明してみる</Link>
            </Button>
          )}
        </li>
      ))}
    </ul>
  );
}
