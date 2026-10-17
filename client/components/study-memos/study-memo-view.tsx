import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/ui/markdown";
import type { StudyMemo } from "@/lib/study-memos";

const SECTION_HEADING =
  "mb-3 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground";

export function StudyMemoView({ memo }: { memo: StudyMemo }) {
  return (
    <div className="mx-auto max-w-4xl px-4 py-6 md:px-6 md:py-8">
      <div className="mb-6 border-l-4 border-muted-foreground/40 pl-4">
        <h1 className="text-2xl font-bold">{memo.topic}</h1>
        {memo.source && (
          <p className="mt-1 text-sm text-muted-foreground">
            教材: {memo.source}
          </p>
        )}
      </div>

      <div className="mb-8">
        <Button asChild variant="brand">
          <Link href={`/learn?memo=${memo.id}`}>説明してみる</Link>
        </Button>
      </div>

      <section aria-labelledby="memo-overview" className="mb-10">
        <h2 id="memo-overview" className={SECTION_HEADING}>
          全体像
        </h2>
        <ul className="space-y-2">
          {memo.overview.map((aspect) => (
            <li
              key={aspect.aspect_id}
              className="rounded-lg border bg-card px-4 py-3"
            >
              <span className="font-medium">{aspect.name}</span>
              {aspect.summary && (
                <Markdown
                  variant="inline"
                  className="mt-1 text-sm text-muted-foreground"
                >
                  {aspect.summary}
                </Markdown>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="memo-glossary" className="mb-10">
        <h2 id="memo-glossary" className={SECTION_HEADING}>
          用語集
        </h2>
        {memo.glossary.length === 0 ? (
          <p className="text-sm text-muted-foreground">用語はありません</p>
        ) : (
          <dl className="space-y-3">
            {memo.glossary.map((entry) => (
              <div
                key={entry.term}
                className="rounded-lg border bg-card px-4 py-3"
              >
                <dt className="font-medium">
                  {entry.reading
                    ? `${entry.term}（${entry.reading}）`
                    : entry.term}
                </dt>
                <dd className="mt-1 text-sm text-muted-foreground">
                  <Markdown variant="inline">{entry.meaning}</Markdown>
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      <section aria-labelledby="memo-questions" className="mb-10">
        <h2 id="memo-questions" className={SECTION_HEADING}>
          疑問と回答
        </h2>
        {memo.questions.length === 0 ? (
          <p className="text-sm text-muted-foreground">疑問はありません</p>
        ) : (
          <ol className="space-y-3">
            {memo.questions.map((item, index) => (
              <li key={index} className="rounded-lg border bg-card px-4 py-3">
                <p className="font-medium">{item.question}</p>
                {item.answer ? (
                  <Markdown
                    variant="inline"
                    className="mt-1 text-sm text-muted-foreground"
                  >
                    {item.answer}
                  </Markdown>
                ) : (
                  <p className="mt-1 text-sm text-muted-foreground">
                    回答の要約はありません
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
