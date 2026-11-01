"use client";

import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import { TooltipLabel } from "@/components/ui/tooltip";
import {
  addDays,
  dayParts,
  type ReflectionSelection,
  type WeekDayStatus,
} from "@/lib/reflection";
import { cn } from "@/lib/utils";

interface DateRailProps {
  days: WeekDayStatus[];
  selected: ReflectionSelection;
  today: string;
  onSelectDay: (day: string) => void;
  onSelectWeek: () => void;
  onPrevWeek: () => void;
  onNextWeek: () => void;
}

const ARROW_CLASS =
  "inline-flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-default disabled:opacity-40 disabled:hover:bg-transparent pointer-coarse:size-11";

export function DateRail({
  days,
  selected,
  today,
  onSelectDay,
  onSelectWeek,
  onPrevWeek,
  onNextWeek,
}: DateRailProps) {
  const weekStart = days[0]?.day ?? today;
  const nextWeekStart = addDays(weekStart, 7);
  const isCurrentWeek = weekStart <= today && today < nextWeekStart;
  const start = dayParts(weekStart);
  const weekLabel = isCurrentWeek
    ? "今週"
    : `${start.month}月${start.date}日の週`;

  return (
    <nav aria-label="振り返る日" className="text-sm">
      <div className="flex items-center justify-between gap-1">
        <span className="pl-1 text-xs text-muted-foreground">{weekLabel}</span>
        <div className="flex items-center">
          <TooltipLabel label="前の週">
            <button
              type="button"
              aria-label="前の週"
              onClick={onPrevWeek}
              className={ARROW_CLASS}
            >
              <ChevronLeftIcon aria-hidden className="size-3.5" />
            </button>
          </TooltipLabel>
          <TooltipLabel label="次の週">
            <button
              type="button"
              aria-label="次の週"
              onClick={onNextWeek}
              disabled={nextWeekStart > today}
              className={ARROW_CLASS}
            >
              <ChevronRightIcon aria-hidden className="size-3.5" />
            </button>
          </TooltipLabel>
        </div>
      </div>
      <div className="mt-2 flex gap-1 md:flex-col md:gap-3">
        <ol className="flex flex-1 gap-0.5 md:flex-col">
          {days.map((status) => (
            <li key={status.day} className="flex-1">
              <DayButton
                status={status}
                selected={
                  selected.kind === "day" && selected.day === status.day
                }
                future={status.day > today}
                onSelect={onSelectDay}
              />
            </li>
          ))}
        </ol>
        <button
          type="button"
          aria-label="今週のまとめ"
          aria-current={selected.kind === "week" ? "true" : undefined}
          onClick={onSelectWeek}
          disabled
          className={cn(
            "flex shrink-0 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-1.5 text-2xs leading-tight text-muted-foreground transition-colors hover:text-foreground disabled:cursor-default disabled:opacity-60 disabled:hover:text-muted-foreground md:flex-row md:justify-start md:px-2 md:py-1.5 md:text-xs",
            selected.kind === "week" &&
              "bg-muted font-semibold text-foreground",
          )}
        >
          <span>今週の</span>
          <span>まとめ</span>
        </button>
      </div>
    </nav>
  );
}

function DayButton({
  status,
  selected,
  future,
  onSelect,
}: {
  status: WeekDayStatus;
  selected: boolean;
  future: boolean;
  onSelect: (day: string) => void;
}) {
  const { month, date, weekday } = dayParts(status.day);
  const label = `${month}月${date}日（${weekday}）${status.unread ? "、未読" : ""}`;
  return (
    <button
      type="button"
      aria-label={label}
      aria-current={selected ? "date" : undefined}
      disabled={future}
      onClick={() => onSelect(status.day)}
      className={cn(
        "flex w-full cursor-pointer flex-col items-center gap-0.5 rounded-lg py-1.5 text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground disabled:cursor-default disabled:opacity-40 disabled:hover:bg-transparent md:flex-row md:justify-between md:px-2 pointer-coarse:min-h-11",
        selected && "bg-muted font-semibold text-foreground hover:bg-muted",
      )}
    >
      <span className="flex flex-col items-center leading-tight md:flex-row md:gap-1.5">
        <span className="text-2xs md:text-sm">{weekday}</span>
        <span>{date}</span>
      </span>
      <span
        aria-hidden
        className={cn(
          "size-1.5 rounded-full",
          status.unread ? "bg-brand" : "bg-transparent",
        )}
      />
    </button>
  );
}
