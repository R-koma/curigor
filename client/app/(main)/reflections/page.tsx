import { headers } from "next/headers";
import { fetchAPI, getToken } from "@/lib/api";
import {
  pickInitialDay,
  toIsoDate,
  weekStartOf,
  type DayReflection,
  type WeekDayStatus,
} from "@/lib/reflection";
import { ReflectionView } from "@/components/reflections/reflection-view";

export const dynamic = "force-dynamic";

export default async function ReflectionsPage() {
  const cookieHeader = (await headers()).get("cookie") ?? "";
  const token = await getToken(cookieHeader);
  const today = toIsoDate(new Date());
  const { days } = await fetchAPI<{ days: WeekDayStatus[] }>(
    `/api/reflections/weeks/${weekStartOf(today)}/days`,
    { token },
  );
  const reflection = await fetchAPI<DayReflection>(
    `/api/reflections/days/${pickInitialDay(days, today)}`,
    { token },
  );

  return (
    <ReflectionView
      initialDays={days}
      initialReflection={reflection}
      today={today}
    />
  );
}
