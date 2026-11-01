"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { DateRail } from "@/components/reflections/date-rail";
import { DayReflectionView } from "@/components/reflections/day-reflection";
import { fetchAPI } from "@/lib/api";
import {
  addDays,
  type DayReflection,
  type ReflectionSelection,
  type WeekDayStatus,
} from "@/lib/reflection";

interface ReflectionViewProps {
  initialDays: WeekDayStatus[];
  initialReflection: DayReflection;
  today: string;
}

type DayState =
  | { status: "ready"; reflection: DayReflection }
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
  const [dayState, setDayState] = useState<DayState>({
    status: "ready",
    reflection: initialReflection,
  });
  const latestDay = useRef(initialReflection.day);
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
      latestDay.current = day;
      setSelected({ kind: "day", day });
      setDayState({ status: "loading" });
      try {
        const reflection = await fetchAPI<DayReflection>(
          `/api/reflections/days/${day}`,
        );
        if (latestDay.current !== day) return;
        setDayState({ status: "ready", reflection });
        markViewed(reflection);
      } catch {
        if (latestDay.current === day) setDayState({ status: "error" });
      }
    },
    [markViewed],
  );

  const loadWeek = useCallback(async (weekStart: string) => {
    latestWeek.current = weekStart;
    try {
      const { days: next } = await fetchAPI<{ days: WeekDayStatus[] }>(
        `/api/reflections/weeks/${weekStart}/days`,
      );
      if (latestWeek.current === weekStart) setDays(next);
    } catch {
      toast.error("週を読み込めませんでした。もう一度お試しください");
    }
  }, []);

  const weekStart = days[0]?.day ?? today;

  return (
    <div className="md:grid md:grid-cols-[8rem_1fr] md:rounded-2xl md:border md:bg-card">
      <aside className="mb-6 md:mb-0 md:border-r md:p-4">
        <DateRail
          days={days}
          selected={selected}
          today={today}
          onSelectDay={(day) => void loadDay(day)}
          onSelectWeek={() => setSelected({ kind: "week" })}
          onPrevWeek={() => void loadWeek(addDays(weekStart, -7))}
          onNextWeek={() => void loadWeek(addDays(weekStart, 7))}
        />
      </aside>
      <div className="min-w-0 md:px-8 md:py-7">
        {dayState.status === "loading" && (
          <div className="flex justify-center py-20">
            <Spinner
              size="lg"
              label="読み込み中"
              className="text-muted-foreground"
            />
          </div>
        )}
        {dayState.status === "error" && selected.kind === "day" && (
          <div className="flex flex-col items-center gap-3 py-20 text-center">
            <p className="text-sm text-muted-foreground">
              この日の振り返りを読み込めませんでした
            </p>
            <Button
              variant="outline"
              onClick={() => void loadDay(selected.day)}
            >
              もう一度読み込む
            </Button>
          </div>
        )}
        {dayState.status === "ready" && (
          <DayReflectionView
            reflection={dayState.reflection}
            isToday={dayState.reflection.day === today}
          />
        )}
      </div>
    </div>
  );
}
