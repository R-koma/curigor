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

export function ReviewStartScreen({
  noteId,
  topic,
  summary,
  focusCount,
  focusAspects,
  onStart,
}: {
  noteId: string;
  topic: string;
  summary: string;
  focusCount: number | null;
  focusAspects: { id: string; name: string }[];
  onStart: (focusAspectIds: string[] | null) => void;
}) {
  const [turnedOff, setTurnedOff] = useState<ReadonlySet<string>>(new Set());
  const toggle = (id: string) =>
    setTurnedOff((current) => {
      const next = new Set(current);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  const start = () =>
    onStart(
      focusAspects.length > 0
        ? focusAspects.map((a) => a.id).filter((id) => !turnedOff.has(id))
        : null,
    );

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
                前回の改善点 {focusCount} 件を、復習の中で重点的に確かめます。
              </p>
            )}
            {focusAspects.length > 0 && (
              <div className="mt-3">
                <p className="mb-2 text-xs text-muted-foreground">
                  重点にする観点を選べます。
                </p>
                <ul className="flex flex-wrap gap-2">
                  {focusAspects.map((aspect) => {
                    const selected = !turnedOff.has(aspect.id);
                    return (
                      <li key={aspect.id}>
                        <Button
                          type="button"
                          variant={selected ? "brand" : "outline"}
                          size="sm"
                          aria-pressed={selected}
                          onClick={() => toggle(aspect.id)}
                        >
                          {selected && <CheckIcon aria-hidden />}
                          {aspect.name}
                        </Button>
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
