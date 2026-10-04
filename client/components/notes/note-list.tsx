"use client";

import { EmptyState } from "@/components/ui/empty-state";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { noteStatusBadge } from "@/lib/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  BookOpenIcon,
  RotateCcwIcon,
  CalendarIcon,
  EllipsisIcon,
  Trash2Icon,
  LayersIcon,
  CheckCircle2Icon,
  ActivityIcon,
  TrendingUpIcon,
  TagIcon,
  LibraryIcon,
  ChevronDownIcon,
} from "lucide-react";
import { fetchAPI } from "@/lib/api";
import {
  foldByCollection,
  type CollectionSummary,
  type NoteListItem,
} from "@/lib/collections";
import { getCategoryOptions, UNCATEGORIZED_LABEL } from "@/lib/note-grouping";

interface NoteResponse {
  id: string;
  topic: string;
  content: string;
  summary: string | null;
  status: string;
  category: string | null;
  collection_id: string | null;
  created_at: string;
  updated_at: string;
  review_count: number;
}

type Filter = "all" | "active" | "archived";

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "すべて" },
  { value: "archived", label: "完了" },
  { value: "active", label: "進行中" },
];

const ALL_CATEGORIES = "all";

export function NoteList({
  notes,
  collections,
}: {
  notes: NoteResponse[];
  collections: CollectionSummary[];
}) {
  const router = useRouter();
  const [openCollections, setOpenCollections] = useState<Set<string>>(
    new Set(),
  );
  const [filter, setFilter] = useState<Filter>("all");
  const [category, setCategory] = useState<string>(ALL_CATEGORIES);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  // 選択肢は全ノート基準で算出し、ステータス絞り込みで候補が消えないようにする
  const categoryOptions = getCategoryOptions(notes);

  const visibleNotes = [...notes]
    .filter((note) => filter === "all" || note.status === filter)
    .filter((note) => {
      if (category === ALL_CATEGORIES) return true;
      const noteCategory = note.category?.trim() || UNCATEGORIZED_LABEL;
      return noteCategory === category;
    })
    .sort((a, b) => b.created_at.localeCompare(a.created_at));

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await fetchAPI(`/api/notes/${id}`, { method: "DELETE" });
      router.refresh();
    } finally {
      setDeletingId(null);
    }
  };

  const renderNoteCard = (note: NoteResponse) => (
    <div
      key={note.id}
      className="group relative rounded-xl border bg-card transition-all duration-200 hover:border-foreground/20 hover:bg-muted/60"
    >
      <Link href={`/notes/${note.id}`} className="block p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex items-center gap-2">
              <span className="truncate font-semibold group-hover:text-primary transition-colors">
                {note.topic}
              </span>
              <Badge
                variant={noteStatusBadge(note.status).variant}
                className="shrink-0 gap-1"
              >
                {note.status === "active" && (
                  <span className="size-1.5 rounded-full bg-current animate-pulse" />
                )}
                {noteStatusBadge(note.status).label}
              </Badge>
            </div>
            {note.summary && (
              <p className="line-clamp-2 text-sm leading-relaxed text-muted-foreground">
                {note.summary}
              </p>
            )}
          </div>
        </div>
        <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <CalendarIcon className="size-3.5" />
            {formatDate(note.created_at)}
          </span>
          <span className="flex items-center gap-1">
            <RotateCcwIcon className="size-3.5" />
            復習回数: {note.review_count}回
          </span>
        </div>
      </Link>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-3 bottom-3"
            disabled={deletingId === note.id}
          >
            <EllipsisIcon className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-auto">
          <DropdownMenuItem
            variant="destructive"
            className="gap-2 px-3"
            onClick={() => setDeleteTargetId(note.id)}
          >
            <Trash2Icon className="size-4" />
            削除
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );

  const collectionNames = Object.fromEntries(
    collections.map((c) => [c.id, c.name]),
  );

  const toggleCollection = (id: string) =>
    setOpenCollections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const renderItem = (item: NoteListItem<NoteResponse>) => {
    if (item.kind === "note") return renderNoteCard(item.note);
    const isOpen = openCollections.has(item.collectionId);
    return (
      <div key={item.collectionId} className="rounded-xl border bg-card">
        <div className="flex items-center justify-between p-5">
          <Link
            href={`/collections/${item.collectionId}`}
            className="flex items-center gap-2 font-semibold hover:text-primary"
          >
            <LibraryIcon className="size-4" />
            {item.name}
          </Link>
          <button
            type="button"
            onClick={() => toggleCollection(item.collectionId)}
            aria-expanded={isOpen}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            {item.notes.length}件のノート
            <ChevronDownIcon
              className={`size-4 transition-transform ${isOpen ? "rotate-180" : ""}`}
            />
          </button>
        </div>
        {isOpen && (
          <div className="space-y-3 border-t p-3">
            {item.notes.map(renderNoteCard)}
          </div>
        )}
      </div>
    );
  };

  const totalNotes = notes.length;
  const activeNotes = notes.filter((n) => n.status === "active").length;
  const archivedNotes = notes.filter((n) => n.status === "archived").length;
  const totalReviews = notes.reduce((sum, n) => sum + n.review_count, 0);

  const stats = [
    {
      label: "ノート総数",
      value: totalNotes,
      icon: LayersIcon,
      colorClass: "text-chart-1",
      bgClass: "bg-chart-1/10",
    },
    {
      label: "進行中",
      value: activeNotes,
      icon: ActivityIcon,
      colorClass: "text-chart-2",
      bgClass: "bg-chart-2/10",
    },
    {
      label: "完了済み",
      value: archivedNotes,
      icon: CheckCircle2Icon,
      colorClass: "text-chart-3",
      bgClass: "bg-chart-3/10",
    },
    {
      label: "累計復習回数",
      value: totalReviews,
      icon: TrendingUpIcon,
      colorClass: "text-chart-4",
      bgClass: "bg-chart-4/10",
    },
  ];

  return (
    <div>
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-xl border bg-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className={`rounded-md p-1.5 ${stat.bgClass}`}>
                <stat.icon className={`size-3.5 ${stat.colorClass}`} />
              </div>
              <span className="text-xs text-muted-foreground">
                {stat.label}
              </span>
            </div>
            <p className="text-2xl font-bold">{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-lg border bg-muted p-1">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`rounded-md px-4 py-1.5 text-sm font-medium transition-all duration-150 cursor-pointer ${
                filter === f.value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {categoryOptions.length > 0 && (
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="h-9 w-44 cursor-pointer gap-2 rounded-lg border-transparent bg-muted px-4 font-medium shadow-none transition-colors hover:bg-muted/70 data-[state=open]:bg-muted/70">
              <TagIcon className="size-3.5 text-muted-foreground" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="rounded-xl">
              <SelectItem value={ALL_CATEGORIES}>すべて</SelectItem>
              {categoryOptions.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {visibleNotes.length === 0 ? (
        <EmptyState icon={BookOpenIcon} title="該当するノートがありません" />
      ) : (
        <div className="space-y-3">
          {foldByCollection(visibleNotes, collectionNames).map(renderItem)}
        </div>
      )}

      <AlertDialog
        open={deleteTargetId !== null}
        onOpenChange={(open) => !open && setDeleteTargetId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>ノートを削除しますか？</AlertDialogTitle>
            <AlertDialogDescription>
              「{notes.find((n) => n.id === deleteTargetId)?.topic}
              」を削除します。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>キャンセル</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteTargetId && handleDelete(deleteTargetId)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              削除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
