import { EmptyState } from "@/components/ui/empty-state";
import { ReflectionActions } from "@/components/reflections/reflection-actions";
import { StruggleAccordion } from "@/components/reflections/struggle-accordion";
import {
  dayParts,
  type WeekReflection,
  type WeekReflectionDay,
} from "@/lib/reflection";

interface WeekReflectionViewProps {
  reflection: WeekReflection;
  isCurrentWeek: boolean;
}

export function WeekReflectionView({
  reflection,
  isCurrentWeek,
}: WeekReflectionViewProps) {
  const { month, date } = dayParts(reflection.week_start);
  const heading = isCurrentWeek
    ? "今週のまとめ"
    : `${month}月${date}日の週のまとめ`;

  if (reflection.days.length === 0) {
    return (
      <div>
        <h2 className="text-2xl font-bold tracking-tight">{heading}</h2>
        <EmptyState title="この週の学習はありません" />
      </div>
    );
  }

  const struggles = reflection.struggles.filter((s) => s.kind === "struggle");
  const questions = reflection.struggles.filter((s) => s.kind === "question");

  return (
    <article>
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <h2 className="text-2xl font-bold tracking-tight">{heading}</h2>
        <ReflectionActions period="week" start={reflection.week_start} />
      </div>
      <div className="mt-4">
        {reflection.days.map((day) => (
          <WeekDaySection key={day.day} day={day} />
        ))}
      </div>
      <div className="mt-6">
        <StruggleAccordion
          variant="struggle"
          items={struggles.map((s) => s.text)}
          topics={struggles.map((s) => s.topic)}
        />
        <StruggleAccordion
          variant="question"
          items={questions.map((s) => ({
            question: s.text,
            answer: s.answer ?? "",
          }))}
          topics={questions.map((s) => s.topic)}
        />
      </div>
    </article>
  );
}

function WeekDaySection({ day }: { day: WeekReflectionDay }) {
  const { month, date, weekday } = dayParts(day.day);
  return (
    <section className="mt-5 first:mt-0">
      <h3 className="border-b pb-1.5 text-xs font-semibold tracking-wide text-muted-foreground">
        {month}月{date}日（{weekday}）
      </h3>
      <ul className="mt-2 space-y-1">
        {day.topics.map((topic, i) => (
          <li key={i} className="text-base font-semibold">
            {topic.topic}
          </li>
        ))}
      </ul>
    </section>
  );
}
