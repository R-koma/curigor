"use client";

import Link from "next/link";
import { ArrowLeftIcon, RotateCcwIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/ui/markdown";

export function ReviewStartScreen({
  noteId,
  topic,
  summary,
  onStart,
}: {
  noteId: string;
  topic: string;
  summary: string;
  onStart: () => void;
}) {
  return (
    <div className="mx-auto max-w-3xl px-4 py-6 md:px-6 md:py-8">
      <Link
        href={`/notes/${noteId}`}
        className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeftIcon className="size-4" aria-hidden />
        ノートに戻る
      </Link>

      <div className="mb-8">
        <p className="flex items-center gap-1.5 text-sm font-medium text-brand-text">
          <RotateCcwIcon className="size-4" aria-hidden />
          復習
        </p>
        <h1 className="mt-2 break-words text-2xl font-bold leading-tight tracking-tight md:text-4xl">
          {topic}
        </h1>
      </div>

      {summary && (
        <section
          aria-labelledby="review-summary-heading"
          className="mb-8 rounded-xl border bg-card p-6"
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

      <Button
        onClick={onStart}
        variant="brand"
        size="lg"
        className="w-full gap-2"
      >
        <RotateCcwIcon className="size-5" aria-hidden />
        復習を開始する
      </Button>
    </div>
  );
}
