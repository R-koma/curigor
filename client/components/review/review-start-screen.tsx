"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeftIcon,
  CheckIcon,
  RotateCcwIcon,
  TargetIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/ui/markdown";

const NO_MEMO_ASPECTS: ReadonlySet<string> = new Set();

function hasMemoAspect(memoAspectIds: ReadonlySet<string>, aspectId: string) {
  for (const id of memoAspectIds) {
    if (id === aspectId || id.startsWith(`${aspectId}-`)) return true;
  }
  return false;
}

export function ReviewStartScreen({
  noteId,
  topic,
  summary,
  focusCount,
  focusAspects,
  memoAspectIds = NO_MEMO_ASPECTS,
  onStart,
}: {
  noteId: string;
  topic: string;
  summary: string;
  focusCount: number | null;
  focusAspects: { id: string; name: string }[];
  memoAspectIds?: ReadonlySet<string>;
  onStart: (focusAspectIds: string[] | null) => void;
}) {
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  const start = () =>
    onStart(
      selected.size > 0
        ? focusAspects.map((a) => a.id).filter((id) => selected.has(id))
        : null,
    );

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
        <h1 className="text-2xl font-bold">復習</h1>
        <p className="mt-1 break-words text-sm text-muted-foreground">
          {topic}
        </p>
      </div>

      <div className="mb-8 space-y-4 empty:hidden">
        {((focusCount !== null && focusCount > 0) ||
          focusAspects.length > 0) && (
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
            {focusCount !== null && focusCount > 0 && (
              <p className="text-sm text-muted-foreground">
                前回の改善点 {focusCount} 件も、復習の中で確かめます。
              </p>
            )}
            {focusAspects.length > 0 && (
              <div className="mt-3">
                <p className="mb-2 text-xs text-muted-foreground">
                  優先して確かめたい観点を選べます。
                </p>
                <ul className="flex flex-wrap gap-2">
                  {focusAspects.map((aspect) => {
                    const isSelected = selected.has(aspect.id);
                    return (
                      <li key={aspect.id} className="flex flex-col gap-1">
                        <Button
                          type="button"
                          variant={isSelected ? "brand" : "outline"}
                          size="sm"
                          aria-pressed={isSelected}
                          onClick={() => toggle(aspect.id)}
                        >
                          {isSelected && <CheckIcon aria-hidden />}
                          {aspect.name}
                        </Button>
                        {hasMemoAspect(memoAspectIds, aspect.id) && (
                          <span className="text-2xs text-muted-foreground">
                            学習メモあり・先に聞きます
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
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

      <Button onClick={start} size="lg" className="w-full gap-2">
        <RotateCcwIcon className="size-5" aria-hidden />
        復習を開始する
      </Button>
    </div>
  );
}
