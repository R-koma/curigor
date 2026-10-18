import Link from "next/link";
import { BookOpenTextIcon } from "lucide-react";
import { formatFeedbackDate } from "@/lib/feedback";
import type { NoteStudyMemo } from "@/lib/study-memos";

export function NoteStudyMemos({ memos }: { memos: NoteStudyMemo[] }) {
  return (
    <section id="study-memos" className="scroll-mt-8 max-md:scroll-mt-14">
      <div className="mb-4 flex items-center gap-2">
        <BookOpenTextIcon className="size-4 text-muted-foreground" />
        <h2 className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
          このノートから作った学習メモ
        </h2>
      </div>
      <ul className="divide-y rounded-lg border bg-card">
        {memos.map((memo) => (
          <li key={memo.id}>
            <Link
              href={`/study-memos/${memo.id}`}
              className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 px-4 py-3 text-sm transition-colors hover:bg-accent/50"
            >
              <span className="min-w-0 break-words">
                {memo.topic}
                {memo.improvement && (
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    {memo.improvement}
                  </span>
                )}
              </span>
              <time
                dateTime={memo.created_at}
                className="text-xs text-muted-foreground"
              >
                {formatFeedbackDate(memo.created_at)}
              </time>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
