"use client";

import { MicIcon } from "lucide-react";
import {
  ALL_SKIPPED_TEXT,
  intakeQuestionText,
  type IntakeAnswers,
  type IntakeCard,
} from "@/lib/intake";
import { cn } from "@/lib/utils";

interface VoiceIntakePromptProps {
  card: IntakeCard;
  disabled?: boolean;
  onSkip: (content: string, answers: IntakeAnswers) => void;
}

export function VoiceIntakePrompt({
  card,
  disabled = false,
  onSkip,
}: VoiceIntakePromptProps) {
  return (
    <div
      className={cn(
        "mt-3 rounded-2xl border bg-background p-4",
        disabled && "pointer-events-none opacity-60",
      )}
    >
      <ol className="space-y-2">
        {card.questions.map((q) => (
          <li key={q.key} className="flex flex-col">
            <span className="text-xs text-muted-foreground">{q.header}</span>
            <span className="text-sm">{intakeQuestionText(q)}</span>
          </li>
        ))}
      </ol>
      <div className="mt-3 flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <MicIcon className="size-3.5 shrink-0" aria-hidden />
          声でまとめて答えてください
        </p>
        <button
          type="button"
          onClick={() =>
            onSkip(ALL_SKIPPED_TEXT, {
              topic: "",
              purpose: "",
              source: [],
              prior_knowledge: "",
            })
          }
          disabled={disabled}
          className="-my-2 -mr-2 inline-flex min-h-11 shrink-0 cursor-pointer items-center rounded-md px-3 text-xs text-muted-foreground hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-1 focus-visible:outline-ring"
        >
          すべてスキップして始める
        </button>
      </div>
    </div>
  );
}
