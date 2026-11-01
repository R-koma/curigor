"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { DateRail } from "@/components/reflections/date-rail";
import { DayReflectionView } from "@/components/reflections/day-reflection";
import { WeekReflectionView } from "@/components/reflections/week-reflection";
import { fetchAPI } from "@/lib/api";
import {
  addDays,
  pickInitialDay,
  type DayReflection,
  type ReflectionSelection,
  type WeekDayStatus,
  type WeekReflection,
} from "@/lib/reflection";

interface ReflectionViewProps {
  initialDays: WeekDayStatus[];
  initialReflection: DayReflection;
  today: string;
}

type ContentState =
  | { status: "day"; reflection: DayReflection }
  | { status: "week"; reflection: WeekReflection }
  | { status: "loading" }
  | { status: "error" };

export function ReflectionView({
  initialDays,
  initialReflection,
  today,
}: ReflectionViewProps) {
  const [days, setDays] = useState(initialDays);
  const [selected, setSelected] = useState<ReflectionSelection>({
    kind: "day",
    day: initialReflection.day,
  });
  const [content, setContent] = useState<ContentState>({
    status: "day",
    reflection: initialReflection,
  });
  const latestRequest = useRef(`day:${initialReflection.day}`);
  const latestWeek = useRef(initialDays[0]?.day);

  const markViewed = useCallback((reflection: DayReflection) => {
    if (reflection.groups.length === 0) return;
    fetchAPI(`/api/reflections/days/${reflection.day}/view`, {
      method: "PUT",
    }).then(
      () =>
        setDays((current) =>
          current.map((d) =>
            d.day === reflection.day ? { ...d, unread: false } : d,
          ),
        ),
      () => undefined,
    );
  }, []);

  useEffect(() => {
    markViewed(initialReflection);
  }, [initialReflection, markViewed]);

  const loadDay = useCallback(
    async (day: string) => {
      const request = `day:${day}`;
      latestRequest.current = request;
      setSelected({ kind: "day", day });
      setContent({ status: "loading" });
      try {
        const reflection = await fetchAPI<DayReflection>(
          `/api/reflections/days/${day}`,
        );
        if (latestRequest.current !== request) return;
        setContent({ status: "day", reflection });
        markViewed(reflection);
      } catch {
        if (latestRequest.current === request) setContent({ status: "error" });
      }
    },
    [markViewed],
  );

  const loadWeekSummary = useCallback(async (weekStart: string) => {
    const request = `week:${weekStart}`;
    latestRequest.current = request;
    setSelected({ kind: "week" });
    setContent({ status: "loading" });
    try {
      const reflection = await fetchAPI<WeekReflection>(
        `/api/reflections/weeks/${weekStart}`,
      );
      if (latestRequest.current === request)
        setContent({ status: "week", reflection });
    } catch {
      if (latestRequest.current === request) setContent({ status: "error" });
    }
  }, []);

  const moveWeek = useCallback(
    async (weekStart: string) => {
      latestWeek.current = weekStart;
      try {
        const { days: next } = await fetchAPI<{ days: WeekDayStatus[] }>(
          `/api/reflections/weeks/${weekStart}/days`,
        );
        if (latestWeek.current !== weekStart) return;
        setDays(next);
        void loadDay(pickInitialDay(next, today));
      } catch {
        toast.error("週を読み込めませんでした。もう一度お試しください");
      }
    },
    [loadDay, today],
  );

  const weekStart = days[0]?.day ?? today;

  return (
    <div className="md:grid md:grid-cols-[8rem_1fr] md:rounded-2xl md:border md:bg-card">
      <aside className="mb-6 md:mb-0 md:border-r md:p-4">
        <DateRail
          days={days}
          selected={selected}
          today={today}
          onSelectDay={(day) => void loadDay(day)}
          onSelectWeek={() => void loadWeekSummary(weekStart)}
          onPrevWeek={() => void moveWeek(addDays(weekStart, -7))}
          onNextWeek={() => void moveWeek(addDays(weekStart, 7))}
        />
      </aside>
      <div className="min-w-0 md:px-8 md:py-7">
        {content.status === "loading" && (
          <div className="flex justify-center py-20">
            <Spinner
              size="lg"
              label="読み込み中"
              className="text-muted-foreground"
            />
          </div>
        )}
        {content.status === "error" && (
          <div className="flex flex-col items-center gap-3 py-20 text-center">
            <p className="text-sm text-muted-foreground">
              {selected.kind === "day"
                ? "この日の振り返りを読み込めませんでした"
                : "この週の振り返りを読み込めませんでした"}
            </p>
            <Button
              variant="outline"
              onClick={() =>
                void (selected.kind === "day"
                  ? loadDay(selected.day)
                  : loadWeekSummary(weekStart))
              }
            >
              もう一度読み込む
            </Button>
          </div>
        )}
        {content.status === "day" && (
          <DayReflectionView
            reflection={content.reflection}
            isToday={content.reflection.day === today}
          />
        )}
        {content.status === "week" && (
          <WeekReflectionView
            reflection={content.reflection}
            isCurrentWeek={
              content.reflection.week_start <= today &&
              today < addDays(content.reflection.week_start, 7)
            }
          />
        )}
      </div>
    </div>
  );
}
