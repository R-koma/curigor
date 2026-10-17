import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/ui/markdown";
import { StudyMemoAspect } from "@/components/study-memos/study-memo-aspect";
import { groupStudyMemo, type StudyMemo } from "@/lib/study-memos";

export function StudyMemoView({ memo }: { memo: StudyMemo }) {
  const groups = groupStudyMemo(memo);
  const date = new Date(memo.created_at).toLocaleDateString("ja-JP");

  return (
    <div className="mx-auto max-w-2xl px-4 pt-6 md:px-6 md:pt-8">
      <header>
        <p className="text-xs text-muted-foreground">
          {memo.source ? `${date} · ${memo.source}` : date}
        </p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">{memo.topic}</h1>
        {memo.summary && (
          <Markdown variant="inline" className="mt-3 text-sm">
            {memo.summary}
          </Markdown>
        )}
      </header>

      {groups.length === 0 ? (
        <p className="mt-8 text-sm text-muted-foreground">
          まだ疑問や用語はありません
        </p>
      ) : (
        <div className="relative mt-8">
          <span
            aria-hidden
            className="absolute top-2 bottom-2 left-3 w-0.5 -translate-x-1/2 bg-border"
          />
          <ol className="relative space-y-5">
            {groups.map((group, index) => (
              <StudyMemoAspect
                key={`${index}:${group.key}`}
                group={group}
                defaultOpen={index === 0}
              />
            ))}
          </ol>
        </div>
      )}

      <div className="sticky bottom-0 mt-6 bg-background py-4">
        <Button asChild variant="brand" className="w-full">
          <Link href={`/learn?memo=${memo.id}`}>説明してみる</Link>
        </Button>
      </div>
    </div>
  );
}
