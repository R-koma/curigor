"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ja } from "date-fns/locale";
import { format } from "date-fns";
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import { fetchAPI } from "@/lib/api";
import { cn } from "@/lib/utils";
import { groupNotesByDate, toLocalDateKey } from "@/lib/group-notes-by-date";
import {
  addMonths,
  buildCalendarWeeks,
  isSameDay,
  startOfMonth,
} from "@/lib/calendar-grid";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

interface CalendarNote {
  id: string;
  topic: string;
  created_at: string;
}

interface CalendarReview {
  id: string;
  note_id: string;
  note_topic: string;
  next_review_at: string;
}

interface DayEntry {
  key: string;
  href: string;
  topic: string;
}

const WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"] as const;

interface SidebarCalendarProps {
  showSkeleton?: boolean;
}

export function SidebarCalendar({ showSkeleton = true }: SidebarCalendarProps) {
  const [notes, setNotes] = useState<CalendarNote[]>([]);
  const [reviews, setReviews] = useState<CalendarReview[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [viewDate, setViewDate] = useState(() => startOfMonth(new Date()));
  const [selected, setSelected] = useState<Date | null>(null);
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const [pickerYear, setPickerYear] = useState(() => new Date().getFullYear());

  // 親が expanded のときだけマウントされるため、初回展開時に一度だけ取得される。
  // 学習（過去のノート）と未来の復習予定をまとめて読み、振り返り兼プランナーにする
  useEffect(() => {
    let active = true;
    Promise.all([
      fetchAPI<{ notes: CalendarNote[] }>("/api/notes").catch(() => ({
        notes: [],
      })),
      fetchAPI<{ review_schedules: CalendarReview[] }>(
        "/api/review-schedules/upcoming",
      ).catch(() => ({ review_schedules: [] })),
    ])
      .then(([noteRes, reviewRes]) => {
        if (!active) return;
        setNotes(noteRes.notes);
        setReviews(reviewRes.review_schedules);
      })
      .finally(() => active && setIsLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const notesByDate = useMemo(() => groupNotesByDate(notes), [notes]);
  const reviewsByDate = useMemo(() => {
    const map = new Map<string, CalendarReview[]>();
    for (const review of reviews) {
      const key = toLocalDateKey(new Date(review.next_review_at));
      const existing = map.get(key);
      if (existing) existing.push(review);
      else map.set(key, [review]);
    }
    return map;
  }, [reviews]);

  const weeks = useMemo(() => buildCalendarWeeks(viewDate), [viewDate]);
  const today = useMemo(() => new Date(), []);
  const todayKey = toLocalDateKey(today);
  // 年をまたぐ1月・12月だけ年を出す。それ以外の月は年度が変わらないため月だけで十分
  const showYear = viewDate.getMonth() === 0 || viewDate.getMonth() === 11;

  const selectedKey = selected ? toLocalDateKey(selected) : null;
  const selectedNotes = selectedKey ? (notesByDate.get(selectedKey) ?? []) : [];
  const selectedReviews = selectedKey
    ? (reviewsByDate.get(selectedKey) ?? [])
    : [];

  const handleSelect = (date: Date) => {
    setSelected(date);
    // 前後の月のマスを押したらその月へ送る
    setViewDate(startOfMonth(date));
  };

  // 前月/翌月/今日ボタンでの月移動は、別の月で選んだ日をその月に残さない。
  // 移動先が当月なら今日を選択扱いにし、そうでなければ選択を解除する
  const goToMonth = (date: Date) => {
    const target = startOfMonth(date);
    setViewDate(target);
    const isTargetCurrentMonth =
      target.getFullYear() === today.getFullYear() &&
      target.getMonth() === today.getMonth();
    setSelected(isTargetCurrentMonth ? today : null);
  };

  const noteEntries: DayEntry[] = selectedNotes.map((note) => ({
    key: note.id,
    href: `/notes/${note.id}`,
    topic: note.topic,
  }));
  const reviewEntries: DayEntry[] = selectedReviews.map((review) => ({
    key: review.id,
    href: `/notes/${review.note_id}`,
    topic: review.note_topic,
  }));

  const renderSection = (
    label: string,
    entries: DayEntry[],
    variant: "learned" | "review",
  ) => (
    <div>
      <p className="mb-1 px-1 text-2xs font-medium text-muted-foreground/70">
        {label}
      </p>
      <ul className="space-y-1">
        {entries.map((entry) => (
          <li key={entry.key}>
            <Link
              href={entry.href}
              className="group flex items-center gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-muted"
              title={entry.topic}
            >
              <span
                className={cn(
                  "size-1.5 shrink-0 rounded-full",
                  variant === "learned" ? "bg-brand" : "border border-warning",
                )}
              />
              <span className="truncate text-xs group-hover:text-primary">
                {entry.topic}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );

  if (isLoading) {
    if (!showSkeleton) return null;
    return (
      <div className="@container mx-auto w-full max-w-[280px] rounded-xl bg-muted/40 p-3">
        <div className="mb-3 flex items-center justify-between px-1">
          <Skeleton className="h-4 w-14 rounded" />
          <div className="flex items-center gap-0.5">
            <Skeleton className="size-6 rounded-full" />
            <Skeleton className="size-6 rounded-full" />
          </div>
        </div>

        <div className="grid grid-cols-7 pb-1.5">
          {WEEKDAYS.map((w) => (
            <Skeleton key={w} className="mx-auto h-3 w-4 rounded" />
          ))}
        </div>

        <div className="flex flex-col gap-1.5">
          <Skeleton className="h-6 w-full rounded-md" />
          <Skeleton className="h-6 w-[90%] rounded-md" />
          <Skeleton className="h-6 w-[95%] rounded-md" />
          <Skeleton className="h-6 w-full rounded-md" />
          <Skeleton className="h-6 w-[88%] rounded-md" />
        </div>

        <div className="mt-2 flex items-center justify-center gap-3">
          <Skeleton className="h-3 w-10 rounded" />
          <Skeleton className="h-3 w-14 rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className="@container mx-auto w-full max-w-[280px] rounded-xl bg-muted/40 p-3">
      <div className="mb-3 flex items-center justify-between px-1">
        <Popover
          open={isPickerOpen}
          onOpenChange={(open) => {
            setIsPickerOpen(open);
            if (open) setPickerYear(viewDate.getFullYear());
          }}
        >
          <PopoverTrigger asChild>
            <button
              type="button"
              className="-ml-1.5 cursor-pointer rounded-md px-1.5 py-0.5 text-sm font-semibold transition-colors hover:bg-muted"
            >
              {format(viewDate, showYear ? "yyyy年 M月" : "M月", {
                locale: ja,
              })}
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-56 p-3">
            <div className="mb-2 flex items-center justify-between px-1">
              <button
                type="button"
                aria-label="前の年"
                onClick={() => setPickerYear((y) => y - 1)}
                className="inline-flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <ChevronLeftIcon className="size-3.5" />
              </button>
              <span className="text-sm font-semibold">{pickerYear}年</span>
              <button
                type="button"
                aria-label="次の年"
                onClick={() => setPickerYear((y) => y + 1)}
                className="inline-flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <ChevronRightIcon className="size-3.5" />
              </button>
            </div>
            <div className="grid grid-cols-4 gap-1">
              {Array.from({ length: 12 }, (_, monthIndex) => {
                const isViewedMonth =
                  pickerYear === viewDate.getFullYear() &&
                  monthIndex === viewDate.getMonth();
                const isCurrentMonth =
                  pickerYear === today.getFullYear() &&
                  monthIndex === today.getMonth();
                return (
                  <button
                    key={monthIndex}
                    type="button"
                    onClick={() => {
                      goToMonth(new Date(pickerYear, monthIndex, 1));
                      setIsPickerOpen(false);
                    }}
                    className={cn(
                      "cursor-pointer rounded-lg py-1.5 text-xs font-medium transition-colors",
                      isViewedMonth
                        ? "bg-brand font-semibold text-brand-foreground"
                        : isCurrentMonth
                          ? "bg-brand-soft text-brand-text"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    {monthIndex + 1}月
                  </button>
                );
              })}
            </div>
          </PopoverContent>
        </Popover>
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            onClick={() => goToMonth(today)}
            className="mr-0.5 cursor-pointer rounded-full bg-brand-soft px-2.5 py-0.5 text-2xs font-semibold text-brand-text transition-colors duration-150 hover:bg-brand/20"
          >
            今日
          </button>
          <button
            type="button"
            aria-label="前の月"
            onClick={() => goToMonth(addMonths(viewDate, -1))}
            className="inline-flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <ChevronLeftIcon className="size-3.5" />
          </button>
          <button
            type="button"
            aria-label="次の月"
            onClick={() => goToMonth(addMonths(viewDate, 1))}
            className="inline-flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <ChevronRightIcon className="size-3.5" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7">
        {WEEKDAYS.map((w) => (
          <div
            key={w}
            className="pb-1.5 text-center text-2xs font-medium text-muted-foreground/70"
          >
            {w}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-0.5">
        {weeks.flat().map(({ date, inCurrentMonth }) => {
          const key = toLocalDateKey(date);
          const isSelected = selected !== null && isSameDay(date, selected);
          const isToday = isSameDay(date, today);
          const isLearned = notesByDate.has(key);
          const hasReview = reviewsByDate.has(key);
          // 過去日（記録なしも閲覧可）と、見せるものがある日（学習/復習予定）のみ操作可能。
          // 本日以降で予定が無い日は色を通常のまま据え置き、クリックしても何もしない
          const isInteractive = key < todayKey || isLearned || hasReview;

          return (
            <button
              key={date.getTime()}
              type="button"
              tabIndex={isInteractive ? undefined : -1}
              onClick={isInteractive ? () => handleSelect(date) : undefined}
              className={cn(
                // 既定色はサイドバーの非アクティブ項目と同じ text-muted-foreground にそろえる
                "relative mx-auto flex aspect-square w-full items-center justify-center rounded-full text-xs text-muted-foreground transition-all duration-150 @[17rem]:text-sm",
                !inCurrentMonth && "text-muted-foreground/40",
                isInteractive ? "cursor-pointer" : "cursor-default",
                // 今日（未選択）: 記録の有無やクリック可否に関わらず常にソフトなブルーの塗りつぶしで区別する
                !isSelected &&
                  isToday &&
                  "bg-brand-soft font-semibold text-brand-text",
                !isSelected &&
                  isInteractive &&
                  (isToday ? "hover:bg-brand/20" : "hover:bg-muted"),
                isSelected &&
                  "bg-brand font-semibold text-brand-foreground shadow-sm shadow-brand/30 hover:bg-brand/90",
              )}
            >
              {date.getDate()}
              {(isLearned || hasReview) && (
                <span className="absolute bottom-1 left-1/2 flex -translate-x-1/2 items-center gap-0.5">
                  {isLearned && (
                    <span
                      className={cn(
                        "size-1 rounded-full",
                        isSelected ? "bg-white" : "bg-brand",
                      )}
                    />
                  )}
                  {hasReview && (
                    <span
                      className={cn(
                        "size-1 rounded-full border",
                        isSelected ? "border-white" : "border-warning",
                      )}
                    />
                  )}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="mt-2 flex items-center justify-center gap-3 text-3xs text-muted-foreground/70">
        <span className="flex items-center gap-1">
          <span className="size-1.5 rounded-full bg-brand" />
          学習
        </span>
        <span className="flex items-center gap-1">
          <span className="size-1.5 rounded-full border border-warning" />
          復習予定
        </span>
      </div>

      {selected && (
        <div className="mt-3 border-t pt-3">
          <div className="mb-2 flex items-center justify-between px-1">
            <span className="text-xs font-semibold">
              {format(selected, "M月d日 (E)", { locale: ja })}
            </span>
            {noteEntries.length + reviewEntries.length > 0 && (
              <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-3xs font-medium text-primary">
                {noteEntries.length + reviewEntries.length}
              </span>
            )}
          </div>
          {noteEntries.length === 0 && reviewEntries.length === 0 ? (
            <p className="px-1 text-xs text-muted-foreground/70">
              この日の学習記録はありません
            </p>
          ) : (
            <div className="space-y-2">
              {noteEntries.length > 0 &&
                renderSection("学習", noteEntries, "learned")}
              {reviewEntries.length > 0 &&
                renderSection("復習予定", reviewEntries, "review")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
