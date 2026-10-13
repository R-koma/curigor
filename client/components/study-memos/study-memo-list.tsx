import Link from "next/link";
import { Button } from "@/components/ui/button";
import type { StudyMemoSummary } from "@/lib/study-memos";

const MAX_MEMOS = 3;

export function StudyMemoList({ memos }: { memos: StudyMemoSummary[] }) {
  const pending = memos.filter((memo) => !memo.handed_over).slice(0, MAX_MEMOS);
  if (pending.length === 0) return null;

  return (
    <section
      aria-labelledby="study-memos-title"
      className="mb-6 rounded-xl border bg-card p-5"
    >
      <h2 id="study-memos-title" className="font-semibold">
        学習メモ
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        AI に教わった内容です。自分の言葉で説明してみましょう。
      </p>
      <ul className="mt-3 space-y-1">
        {pending.map((memo) => (
          <li key={memo.id} className="flex items-center gap-2">
            <Link
              href={`/study-memos/${memo.id}`}
              className="flex min-w-0 flex-1 items-center justify-between gap-3 rounded-lg px-2 py-2 hover:bg-muted"
            >
              <span className="truncate">{memo.topic}</span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {new Date(memo.created_at).toLocaleDateString("ja-JP")}
              </span>
            </Link>
            <Button asChild size="sm" variant="outline" className="shrink-0">
              <Link href={`/learn?memo=${memo.id}`}>説明してみる</Link>
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}
