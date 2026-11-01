import {
  BookOpenIcon,
  MicIcon,
  RefreshCwIcon,
  type LucideIcon,
} from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { ReflectionActions } from "@/components/reflections/reflection-actions";
import { StruggleAccordion } from "@/components/reflections/struggle-accordion";
import {
  SESSION_TYPE_LABELS,
  dayParts,
  type DayReflection,
  type ReflectionGroup,
  type ReflectionSessionType,
  type ReflectionTopic,
} from "@/lib/reflection";

const GROUP_ICONS: Readonly<Record<ReflectionSessionType, LucideIcon>> = {
  learning: MicIcon,
  explore: BookOpenIcon,
  review: RefreshCwIcon,
};

interface DayReflectionViewProps {
  reflection: DayReflection;
  isToday: boolean;
}

export function DayReflectionView({
  reflection,
  isToday,
}: DayReflectionViewProps) {
  const { month, date, weekday } = dayParts(reflection.day);
  const eyebrow = (
    <p className="text-xs tracking-wide text-muted-foreground">
      {month}月{date}日（{weekday}）
    </p>
  );

  if (reflection.groups.length === 0) {
    return (
      <div>
        {eyebrow}
        <EmptyState title="この日の学習はありません" />
      </div>
    );
  }

  const showGroupHeadings = reflection.groups.length > 1;

  return (
    <article>
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          {eyebrow}
          <h2 className="mt-1 text-2xl font-bold tracking-tight">
            {isToday ? "今日学んだこと" : `${month}月${date}日に学んだこと`}
          </h2>
        </div>
        <ReflectionActions period="day" start={reflection.day} />
      </div>
      <div className="mt-2">
        {reflection.groups.map((group) => (
          <ReflectionGroupSection
            key={group.session_type}
            group={group}
            showHeading={showGroupHeadings}
          />
        ))}
      </div>
    </article>
  );
}

function ReflectionGroupSection({
  group,
  showHeading,
}: {
  group: ReflectionGroup;
  showHeading: boolean;
}) {
  const Icon = GROUP_ICONS[group.session_type];
  return (
    <section className="mt-6 first:mt-4">
      {showHeading && (
        <h3 className="flex items-center gap-2 border-b pb-1.5 text-xs font-semibold tracking-wide text-muted-foreground">
          <Icon aria-hidden className="size-3.5" />
          {SESSION_TYPE_LABELS[group.session_type]}
        </h3>
      )}
      {group.topics.map((topic) => (
        <TopicBlock
          key={`${topic.session_type}-${topic.source_id}`}
          topic={topic}
          headingLevel={showHeading ? "h4" : "h3"}
        />
      ))}
    </section>
  );
}

function TopicBlock({
  topic,
  headingLevel: Heading,
}: {
  topic: ReflectionTopic;
  headingLevel: "h3" | "h4";
}) {
  return (
    <div className="mt-4">
      <Heading className="text-base font-semibold">{topic.topic}</Heading>
      <p className="mt-1 text-prose leading-relaxed text-foreground/85">
        {topic.summary}
      </p>
      <StruggleAccordion variant="struggle" items={topic.struggles} />
      <StruggleAccordion variant="question" items={topic.questions} />
    </div>
  );
}
