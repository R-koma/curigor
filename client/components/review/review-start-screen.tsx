import Link from "next/link";
import { ArrowLeftIcon, RotateCcwIcon, TargetIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/ui/markdown";

export function ReviewStartScreen({
  noteId,
  topic,
  summary,
  focusCount,
  onStart,
}: {
  noteId: string;
  topic: string;
  summary: string;
  focusCount: number | null;
  onStart: () => void;
}) {
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <Link
        href={`/notes/${noteId}`}
        className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeftIcon className="size-4" aria-hidden />
        ノートに戻る
      </Link>

      <div className="mb-8">
        <h1 className="text-2xl font-bold">復習</h1>
        <p className="mt-1 break-words text-sm text-muted-foreground">
          {topic}
        </p>
      </div>

      <div className="mb-8 space-y-4 empty:hidden">
        {focusCount !== null && focusCount > 0 && (
          <section
            aria-labelledby="review-focus-heading"
            className="rounded-xl border bg-card p-6"
          >
            <h2
              id="review-focus-heading"
              className="mb-2 flex items-center gap-2 text-sm font-semibold"
            >
              <TargetIcon className="size-4" aria-hidden />
              今回の重点
            </h2>
            <p className="text-sm text-muted-foreground">
              前回の改善点 {focusCount} 件を、復習の中で重点的に確かめます。
            </p>
          </section>
        )}

        {summary && (
          <section
            aria-labelledby="review-summary-heading"
            className="rounded-xl border bg-card p-6"
          >
            <h2
              id="review-summary-heading"
              className="mb-3 text-sm font-semibold"
            >
              前回の要約
            </h2>
            <Markdown>{summary}</Markdown>
          </section>
        )}
      </div>

      <Button onClick={onStart} size="lg" className="w-full gap-2">
        <RotateCcwIcon className="size-5" aria-hidden />
        復習を開始する
      </Button>
    </div>
  );
}
