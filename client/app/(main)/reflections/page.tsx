import { headers } from "next/headers";
import { fetchAPI, getToken } from "@/lib/api";
import {
  parseReflectionTarget,
  pickInitialDay,
  toIsoDate,
  weekStartOf,
  type DayReflection,
  type WeekDayStatus,
  type WeekReflection,
} from "@/lib/reflection";
import { ReflectionView } from "@/components/reflections/reflection-view";

export const dynamic = "force-dynamic";

interface ReflectionsPageProps {
  searchParams: Promise<{ day?: string | string[]; week?: string | string[] }>;
}

export default async function ReflectionsPage({
  searchParams,
}: ReflectionsPageProps) {
  const cookieHeader = (await headers()).get("cookie") ?? "";
  const token = await getToken(cookieHeader);
  const today = toIsoDate(new Date());
  const target = parseReflectionTarget(await searchParams, today);

  const weekStart =
    target === null
      ? weekStartOf(today)
      : target.kind === "day"
        ? weekStartOf(target.day)
        : target.weekStart;
  const { days } = await fetchAPI<{ days: WeekDayStatus[] }>(
    `/api/reflections/weeks/${weekStart}/days`,
    { token },
  );

  if (target?.kind === "week") {
    const reflection = await fetchAPI<WeekReflection>(
      `/api/reflections/weeks/${target.weekStart}`,
      { token },
    );
    return (
      <ReflectionView
        initialDays={days}
        initial={{ kind: "week", reflection }}
        today={today}
      />
    );
  }

  const day = target?.kind === "day" ? target.day : pickInitialDay(days, today);
  const reflection = await fetchAPI<DayReflection>(
    `/api/reflections/days/${day}`,
    { token },
  );
  return (
    <ReflectionView
      initialDays={days}
      initial={{ kind: "day", reflection }}
      today={today}
    />
  );
}
