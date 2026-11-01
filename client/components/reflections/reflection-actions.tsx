import { ReflectionAudio } from "@/components/reflections/reflection-audio";
import type { ReflectionPeriod } from "@/lib/reflection";

interface ReflectionActionsProps {
  period: ReflectionPeriod;
  start: string;
}

export function ReflectionActions({ period, start }: ReflectionActionsProps) {
  return (
    <div className="flex flex-wrap items-start gap-2">
      <ReflectionAudio period={period} start={start} />
    </div>
  );
}
