import Link from "next/link";
import { CheckIcon, NotebookPenIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { StudyMemoAspectName, StudyMemoSummary } from "@/lib/study-memos";
import { cn } from "@/lib/utils";

const MAX_ASPECTS = 3;

function memoDate(iso: string): string {
  const date = new Date(iso);
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return date.toLocaleDateString("ja-JP", {
    year: sameYear ? undefined : "numeric",
    month: "long",
    day: "numeric",
  });
}

function AspectChips({ aspects }: { aspects: StudyMemoAspectName[] }) {
  if (aspects.length === 0) return null;
  const ordered = [
    ...aspects.filter((a) => a.is_core),
    ...aspects.filter((a) => !a.is_core),
  ];
  const shown = ordered.slice(0, MAX_ASPECTS);
  const rest = ordered.length - shown.length;

  return (
    <ul aria-label="観点" className="mt-3 flex flex-wrap gap-1.5">
      {shown.map((aspect) => (
        <li
          key={aspect.name}
          className={cn(
            "rounded-md px-2 py-0.5 text-xs",
            aspect.is_core
              ? "bg-brand-soft text-brand-text"
              : "bg-muted text-foreground",
          )}
        >
          {aspect.name}
        </li>
      ))}
      {rest > 0 && (
        <li className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          +{rest}
        </li>
      )}
    </ul>
  );
}

function StudyMemoCard({ memo }: { memo: StudyMemoSummary }) {
  return (
    <li
      className={cn(
        "relative rounded-xl border bg-card p-5 transition-colors hover:bg-muted/60",
        memo.handed_over && "opacity-75",
      )}
    >
      <div className="flex items-start gap-3">
        <Link
          href={`/study-memos/${memo.id}`}
          className="min-w-0 flex-1 font-semibold after:absolute after:inset-0 after:rounded-xl"
        >
          {memo.topic}
        </Link>
        {memo.handed_over ? (
          <Badge variant="success" className="shrink-0">
            <CheckIcon aria-hidden />
            説明済み
          </Badge>
        ) : (
          <Badge variant="info" className="shrink-0">
            説明待ち
          </Badge>
        )}
      </div>
      <AspectChips aspects={memo.aspects} />
      <p className="mt-3 flex gap-4 text-xs text-muted-foreground">
        <span>
          用語{" "}
          <span className="font-semibold text-foreground">
            {memo.glossary_count}
          </span>
        </span>
        <span>
          疑問{" "}
          <span className="font-semibold text-foreground">
            {memo.question_count}
          </span>
        </span>
      </p>
      <div className="mt-4 flex items-center justify-between gap-3 border-t pt-3">
        <span className="min-w-0 truncate text-xs text-muted-foreground">
          {memoDate(memo.created_at)}
          {memo.source && ` · ${memo.source}`}
        </span>
        {!memo.handed_over && (
          <Button
            asChild
            size="sm"
            variant="brand"
            className="relative z-raised shrink-0 pointer-coarse:h-11 pointer-coarse:px-4"
          >
            <Link href={`/learn?memo=${memo.id}`}>説明してみる</Link>
          </Button>
        )}
      </div>
    </li>
  );
}

export function StudyMemoList({ memos }: { memos: StudyMemoSummary[] }) {
  if (memos.length === 0) {
    return (
      <EmptyState
        icon={NotebookPenIcon}
        title="学習メモはありません。"
        description="AI と理解を深めると、その内容がここに残ります。"
        action={
          <Button
            asChild
            variant="outline"
            size="sm"
            className="pointer-coarse:h-11 pointer-coarse:px-4"
          >
            <Link href="/learn?mode=explore">理解する</Link>
          </Button>
        }
      />
    );
  }

  return (
    <ul className="space-y-3">
      {memos.map((memo) => (
        <StudyMemoCard key={memo.id} memo={memo} />
      ))}
    </ul>
  );
}
