import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/ui/markdown";
import { StudyMemoActionsMenu } from "@/components/study-memos/study-memo-actions-menu";
import { StudyMemoAspect } from "@/components/study-memos/study-memo-aspect";
import { groupStudyMemo, type StudyMemo } from "@/lib/study-memos";

export function StudyMemoView({ memo }: { memo: StudyMemo }) {
  const groups = groupStudyMemo(memo);
  const date = new Date(memo.created_at).toLocaleDateString("ja-JP");

  return (
    <div className="mx-auto max-w-2xl px-4 pt-6 md:px-6 md:pt-8">
      <header>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">
              {memo.source ? `${date} · ${memo.source}` : date}
            </p>
            <h1 className="mt-1 text-2xl font-bold tracking-tight">
              {memo.topic}
            </h1>
          </div>
          <StudyMemoActionsMenu memoId={memo.id} topic={memo.topic} />
        </div>
        {memo.summary && (
          <section
            aria-labelledby="study-memo-summary"
            className="mt-4 rounded-xl bg-muted/50 px-4 py-3"
          >
            <h2
              id="study-memo-summary"
              className="text-2xs tracking-wider text-muted-foreground"
            >
              要約
            </h2>
            <Markdown variant="inline" className="mt-1 text-sm">
              {memo.summary}
            </Markdown>
          </section>
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

      <div className="sticky bottom-0 mt-6 border-t border-border bg-background py-4">
        <Button asChild variant="brand" className="w-full">
          <Link href={`/learn?memo=${memo.id}`}>説明してみる</Link>
        </Button>
      </div>
    </div>
  );
}
