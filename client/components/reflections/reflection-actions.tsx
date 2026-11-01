"use client";

import { useState } from "react";
import { ListChecksIcon } from "lucide-react";
import { ReflectionAudio } from "@/components/reflections/reflection-audio";
import { ReflectionQuizDialog } from "@/components/reflections/reflection-quiz-dialog";
import { Button } from "@/components/ui/button";
import type { ReflectionPeriod } from "@/lib/reflection";

interface ReflectionActionsProps {
  period: ReflectionPeriod;
  start: string;
}

export function ReflectionActions({ period, start }: ReflectionActionsProps) {
  const [quizOpen, setQuizOpen] = useState(false);
  return (
    <div className="flex flex-wrap items-start gap-2">
      <ReflectionAudio period={period} start={start} />
      <Button variant="outline" size="sm" onClick={() => setQuizOpen(true)}>
        <ListChecksIcon aria-hidden />
        小テスト
      </Button>
      <ReflectionQuizDialog
        period={period}
        start={start}
        open={quizOpen}
        onOpenChange={setQuizOpen}
      />
    </div>
  );
}
