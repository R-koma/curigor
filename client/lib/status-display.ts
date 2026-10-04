import {
  AlertCircleIcon,
  CheckCircle2Icon,
  CheckCircleIcon,
  CircleDashedIcon,
  CircleDotIcon,
  type LucideIcon,
} from "lucide-react";

import type { Tone } from "@/lib/tone";

export type Urgency = "overdue" | "today" | "tomorrow" | "later";

export function getUrgency(
  nextReviewAt: string,
  now: Date = new Date(),
): Urgency {
  const reviewDate = new Date(nextReviewAt);
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrowStart = new Date(todayStart);
  tomorrowStart.setDate(tomorrowStart.getDate() + 1);
  const dayAfterStart = new Date(tomorrowStart);
  dayAfterStart.setDate(dayAfterStart.getDate() + 1);

  if (reviewDate < todayStart) return "overdue";
  if (reviewDate < tomorrowStart) return "today";
  if (reviewDate < dayAfterStart) return "tomorrow";
  return "later";
}

export const URGENCY_DISPLAY: Record<
  Urgency,
  { label: string; tone: Tone; leftBorder: string }
> = {
  overdue: {
    label: "期限切れ",
    tone: "danger",
    leftBorder: "border-l-destructive",
  },
  today: { label: "今日", tone: "caution", leftBorder: "border-l-caution" },
  tomorrow: { label: "明日", tone: "warning", leftBorder: "border-l-warning" },
  later: { label: "それ以降", tone: "success", leftBorder: "border-l-success" },
};

export type Coverage = "covered" | "partial" | "uncovered";

export const COVERAGE_DISPLAY: Record<
  Coverage,
  { label: string; icon: LucideIcon; tone: Tone }
> = {
  covered: { label: "カバー済み", icon: CheckCircle2Icon, tone: "success" },
  partial: { label: "部分的", icon: CircleDotIcon, tone: "warning" },
  uncovered: { label: "未カバー", icon: CircleDashedIcon, tone: "neutral" },
};

export type FeedbackKind = "positive" | "improvement";

export const FEEDBACK_DISPLAY: Record<
  FeedbackKind,
  { tone: Tone; icon: LucideIcon }
> = {
  positive: { tone: "success", icon: CheckCircleIcon },
  improvement: { tone: "warning", icon: AlertCircleIcon },
};
