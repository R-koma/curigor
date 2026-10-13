import Link from "next/link";
import type { StudyMemoSummary } from "@/lib/study-memos";

const MAX_MEMOS = 3;

export function StudyMemoList({ memos }: { memos: StudyMemoSummary[] }) {
  if (memos.length === 0) return null;

  return (
    <section
      aria-labelledby="study-memos-title"
      className="mb-6 rounded-xl border bg-card p-5"
    >
      <h2 id="study-memos-title" className="font-semibold">
        学習メモ
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        AI に教わった内容の記録です。
      </p>
      <ul className="mt-3 space-y-1">
        {memos.slice(0, MAX_MEMOS).map((memo) => (
          <li key={memo.id}>
            <Link
              href={`/study-memos/${memo.id}`}
              className="flex items-center justify-between gap-3 rounded-lg px-2 py-2 hover:bg-muted"
            >
              <span className="truncate">{memo.topic}</span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {new Date(memo.created_at).toLocaleDateString("ja-JP")}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
