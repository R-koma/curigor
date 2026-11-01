import type { StudyMemoQuestion } from "@/lib/study-memos";

export type ReflectionSessionType = "learning" | "explore" | "review";

export interface ReflectionTopic {
  session_type: ReflectionSessionType;
  source_id: string;
  topic: string;
  summary: string;
  struggles: string[];
  questions: StudyMemoQuestion[];
}

export interface ReflectionGroup {
  session_type: ReflectionSessionType;
  topics: ReflectionTopic[];
}

export interface DayReflection {
  day: string;
  groups: ReflectionGroup[];
}

export interface WeekDayStatus {
  day: string;
  has_learning: boolean;
  unread: boolean;
}

export interface WeekTopic {
  session_type: ReflectionSessionType;
  topic: string;
}

export interface WeekReflectionDay {
  day: string;
  topics: WeekTopic[];
}

export interface WeekStruggle {
  topic: string;
  kind: "struggle" | "question";
  text: string;
  answer: string | null;
}

export interface WeekReflection {
  week_start: string;
  days: WeekReflectionDay[];
  struggles: WeekStruggle[];
}

export type ReflectionPeriod = "day" | "week";

export type ReflectionSelection =
  { kind: "day"; day: string } | { kind: "week" };

export const SESSION_TYPE_LABELS: Readonly<
  Record<ReflectionSessionType, string>
> = {
  learning: "説明して学ぶ",
  explore: "インプット",
  review: "復習",
};

const WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"] as const;

const ISO_DATE_FORMAT = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Tokyo",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function toIsoDate(d: Date): string {
  return ISO_DATE_FORMAT.format(d);
}

function parseIso(iso: string): Date {
  return new Date(`${iso}T00:00:00Z`);
}

export function addDays(iso: string, n: number): string {
  const d = parseIso(iso);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export function weekStartOf(iso: string): string {
  const offset = (parseIso(iso).getUTCDay() + 6) % 7;
  return addDays(iso, -offset);
}

export function dayParts(iso: string): {
  month: number;
  date: number;
  weekday: string;
} {
  const d = parseIso(iso);
  return {
    month: d.getUTCMonth() + 1,
    date: d.getUTCDate(),
    weekday: WEEKDAYS[d.getUTCDay()],
  };
}

export function pickInitialDay(days: WeekDayStatus[], today: string): string {
  const learned = days.filter((d) => d.has_learning && d.day <= today);
  if (learned.length > 0) return learned[learned.length - 1].day;
  if (days.length === 0 || days.some((d) => d.day === today)) return today;
  return days[0].day;
}
