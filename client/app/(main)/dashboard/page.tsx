"use client";

import { EmptyState } from "@/components/ui/empty-state";
import { useEffect, useState } from "react";
import Link from "next/link";
import { authClient } from "@/lib/auth-client";
import { fetchAPI } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { getUrgency, URGENCY_DISPLAY } from "@/lib/status-display";
import { TONE_CLASSES } from "@/lib/tone";
import {
  PlusIcon,
  BookOpenIcon,
  RotateCcwIcon,
  ClockIcon,
  SparklesIcon,
  TrendingUpIcon,
} from "lucide-react";

interface ReviewSchedule {
  id: string;
  note_id: string;
  review_count: number;
  next_review_at: string;
  note_topic: string;
  note_summary: string;
}

export default function DashBoard() {
  const { data: session, isPending } = authClient.useSession();
  const [reviews, setReviews] = useState<ReviewSchedule[]>([]);
  const [completedToday, setCompletedToday] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!session) return;
    fetchAPI<{ review_schedules: ReviewSchedule[]; completed_today: number }>(
      "/api/review-schedules",
    )
      .then(({ review_schedules, completed_today }) => {
        setReviews(review_schedules);
        setCompletedToday(completed_today);
      })
      .catch(() => {
        setReviews([]);
        setCompletedToday(0);
      })
      .finally(() => setIsLoading(false));
  }, [session]);

  const pendingCount = reviews.length;
  const totalCount = pendingCount + completedToday;
  const progressPercent =
    totalCount > 0 ? (completedToday / totalCount) * 100 : 0;
  const allDone = totalCount > 0 && pendingCount === 0;

  if (isPending || isLoading) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-8">
        <div className="mb-6 flex items-start justify-between">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-9 w-44 rounded-lg" />
        </div>
        <Skeleton className="mb-6 h-24 w-full rounded-xl" />
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-xl border bg-card p-5 space-y-3">
              <div className="flex items-center gap-2">
                <Skeleton className="h-4 w-4 rounded" />
                <Skeleton className="h-5 w-3/5" />
              </div>
              <Skeleton className="h-4 w-4/5 ml-6" />
              <Skeleton className="h-3 w-2/5 ml-6" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!session) return null;

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-8 flex items-start justify-between">
        <div className="border-l-4 border-brand pl-4">
          <h1 className="text-2xl font-bold">今日の復習</h1>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-3">
          <Button
            asChild
            variant="brand"
            className="gap-2 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-brand/30 active:translate-y-0 active:shadow-sm"
          >
            <Link href="/learn">
              <PlusIcon className="h-5 w-5 transition-transform duration-200 group-hover/button:rotate-90" />
              新規学習
            </Link>
          </Button>
        </div>
      </div>

      {totalCount > 0 && (
        <div className="mb-6 rounded-xl border bg-card p-5">
          <div className="mb-3 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-sm font-medium">
              <TrendingUpIcon className="h-4 w-4 text-brand-text" />
              進捗
            </span>
            <span className="text-sm text-muted-foreground">
              {completedToday} / {totalCount} 件完了
            </span>
          </div>
          <Progress value={progressPercent} className="h-2 [&>div]:bg-brand" />
          {allDone && (
            <p className="mt-3 flex items-center gap-1.5 text-xs font-medium text-success-text">
              <SparklesIcon className="h-3.5 w-3.5" />
              今日の復習をすべて完了しました！
            </p>
          )}
        </div>
      )}

      <section>
        {reviews.length === 0 ? (
          <EmptyState
            icon={SparklesIcon}
            title="復習が必要なノートはありません"
            className="rounded-xl border bg-card py-16"
          />
        ) : (
          <div className="space-y-3">
            {reviews.map((review) => {
              const urgency = getUrgency(review.next_review_at);
              const { label, tone, leftBorder } = URGENCY_DISPLAY[urgency];

              return (
                <div
                  key={review.id}
                  className={`group rounded-xl border border-l-4 bg-card transition-all duration-200 hover:border-foreground/20 hover:shadow-lg hover:-translate-y-0.5 ${leftBorder}`}
                >
                  <Link href={`/notes/${review.note_id}`} className="block p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex items-center gap-2">
                          <BookOpenIcon className="h-4 w-4 text-primary shrink-0" />
                          <span className="truncate font-semibold transition-colors group-hover:text-primary">
                            {review.note_topic}
                          </span>
                        </div>
                        {review.note_summary && (
                          <p className="line-clamp-1 pl-6 text-sm text-muted-foreground">
                            {review.note_summary}
                          </p>
                        )}
                      </div>
                      <Badge variant="warning" className="shrink-0 gap-1">
                        <RotateCcwIcon className="h-3 w-3" />
                        {review.review_count}
                        <span>回目</span>
                      </Badge>
                    </div>
                    <div className="mt-3 flex items-center gap-3 pl-6 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <ClockIcon className="h-3 w-3" />
                        {new Date(review.next_review_at).toLocaleDateString(
                          "ja-JP",
                        )}
                        までに復習
                      </span>
                      <span
                        className={`font-medium ${TONE_CLASSES[tone].text}`}
                      >
                        {label}
                      </span>
                    </div>
                  </Link>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
