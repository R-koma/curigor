import Link from "next/link";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  PencilIcon,
  RotateCcwIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { noteStatusBadge } from "@/lib/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { NoteShareButton } from "@/components/notes/note-share-button";
import { NoteCategoryEditor } from "@/components/notes/note-category-editor";

interface NoteHeaderProps {
  id: string;
  topic: string;
  status: string;
  category: string | null;
  createdAt: string;
  updatedAt: string;
  reviewCount: number;
  summary: string;
  content: string;
  isEditing?: boolean;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

export function NoteDates({
  createdAt,
  updatedAt,
  className,
}: {
  createdAt: string;
  updatedAt: string;
  className?: string;
}) {
  return (
    <>
      <span className={className}>作成 {formatDate(createdAt)}</span>
      {updatedAt !== createdAt && (
        <span className={className}>更新 {formatDate(updatedAt)}</span>
      )}
    </>
  );
}

export function NoteHeader({
  id,
  topic,
  status,
  category,
  createdAt,
  updatedAt,
  reviewCount,
  summary,
  content,
  isEditing = false,
}: NoteHeaderProps) {
  const statusBadge = noteStatusBadge(status);

  return (
    <header className="mb-6 md:mb-12">
      <Link
        href="/notes"
        aria-label="ノート一覧に戻る"
        className="-ml-1 mb-3 inline-flex min-h-9 items-center gap-0.5 text-sm text-muted-foreground transition-colors hover:text-foreground pointer-coarse:min-h-11 md:hidden"
      >
        <ChevronLeftIcon className="size-4" aria-hidden />
        ノート一覧
      </Link>
      <nav
        aria-label="パンくずリスト"
        className="mb-6 hidden items-center gap-1.5 text-sm text-muted-foreground md:flex"
      >
        <Link href="/notes" className="transition-colors hover:text-foreground">
          ノート一覧
        </Link>
        <ChevronRightIcon className="size-3.5 shrink-0" />
        <span className="truncate text-foreground">{topic}</span>
      </nav>
      <div className="flex items-start gap-3 md:flex-row md:items-end md:justify-between md:gap-6">
        <div className="min-w-0 flex-1">
          {!isEditing && (
            <h1 className="text-xl font-bold tracking-tight md:text-3xl lg:text-4xl">
              {topic}
            </h1>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted-foreground md:mt-4 md:gap-x-4">
            <Badge variant={statusBadge.variant} className="gap-1 font-normal">
              {status === "active" && (
                <span className="size-1.5 rounded-full bg-current animate-pulse" />
              )}
              {statusBadge.label}
            </Badge>
            <NoteCategoryEditor noteId={id} category={category} />
            <NoteDates
              createdAt={createdAt}
              updatedAt={updatedAt}
              className="max-md:hidden"
            />
            {reviewCount > 0 && <span>復習 {reviewCount} 回</span>}
          </div>
        </div>
        {!isEditing && (
          <div className="flex shrink-0 gap-2 md:flex-wrap md:gap-3">
            <Tooltip>
              <TooltipTrigger asChild>
                <Link
                  href={`/notes/${id}?edit=1`}
                  aria-label="ノートを編集"
                  className={buttonVariants({
                    variant: "outline",
                    size: "icon-lg",
                  })}
                >
                  <PencilIcon className="size-4" />
                </Link>
              </TooltipTrigger>
              <TooltipContent>ノートを編集</TooltipContent>
            </Tooltip>
            <NoteShareButton
              topic={topic}
              summary={summary}
              content={content}
            />
            <Button asChild size="lg" className="gap-2 max-md:hidden">
              <Link href={`/review/${id}`}>
                <RotateCcwIcon className="size-4" />
                復習する
              </Link>
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
