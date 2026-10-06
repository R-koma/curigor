import Link from "next/link";
import { ChevronRightIcon, PencilIcon, RotateCcwIcon } from "lucide-react";
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
    <header className="mb-12">
      <nav className="mb-6 flex items-center gap-1.5 text-sm text-muted-foreground">
        <Link href="/notes" className="transition-colors hover:text-foreground">
          ノート一覧
        </Link>
        <ChevronRightIcon className="size-3.5 shrink-0" />
        <span className="truncate text-foreground">{topic}</span>
      </nav>
      <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0 flex-1">
          {!isEditing && (
            <h1 className="text-3xl font-bold tracking-tight md:text-4xl">
              {topic}
            </h1>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
            <Badge variant={statusBadge.variant} className="gap-1 font-normal">
              {status === "active" && (
                <span className="size-1.5 rounded-full bg-current animate-pulse" />
              )}
              {statusBadge.label}
            </Badge>
            <NoteCategoryEditor noteId={id} category={category} />
            <span>作成 {formatDate(createdAt)}</span>
            {updatedAt !== createdAt && (
              <span>更新 {formatDate(updatedAt)}</span>
            )}
            {reviewCount > 0 && <span>復習 {reviewCount} 回</span>}
          </div>
        </div>
        {!isEditing && (
          <div className="flex flex-wrap gap-3 md:shrink-0">
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
            <Button asChild size="lg" className="gap-2">
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
