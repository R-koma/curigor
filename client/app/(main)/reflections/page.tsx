import { headers } from "next/headers";
import { fetchAPI, getToken } from "@/lib/api";
import { PAGE_TITLES } from "@/lib/nav-links";
import {
  pickInitialDay,
  toIsoDate,
  weekStartOf,
  type DayReflection,
  type WeekDayStatus,
} from "@/lib/reflection";
import { PageHeading } from "@/components/layout/page-heading";
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
    <div className="mx-auto max-w-5xl px-4 py-6 md:px-6 md:py-8">
      <div className="mb-6 max-md:mb-0">
        <PageHeading title={PAGE_TITLES["/reflections"]} />
      </div>
      <ReflectionView
        initialDays={days}
        initialReflection={reflection}
        today={today}
      />
    </div>
  );
}
