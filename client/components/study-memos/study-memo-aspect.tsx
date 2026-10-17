"use client";

import { useId, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Markdown } from "@/components/ui/markdown";
import { TooltipLabel } from "@/components/ui/tooltip";
import { StudyMemoCard } from "@/components/study-memos/study-memo-card";
import type { StudyMemoGroup } from "@/lib/study-memos";
import { cn } from "@/lib/utils";

export function StudyMemoAspect({
  group,
  defaultOpen,
}: {
  group: StudyMemoGroup;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const contentId = useId();
  const label = `${group.name}を${open ? "閉じる" : "開く"}`;
  const Icon = open ? ChevronUp : ChevronDown;

  return (
    <li className="flex">
      <span
        aria-hidden
        className="flex h-5 w-6 shrink-0 items-center justify-center"
      >
        {group.isCore ? (
          <span className="size-3 rounded-full bg-brand ring-3 ring-brand-soft" />
        ) : (
          <span className="size-2.5 rounded-full border-2 border-muted-foreground bg-background" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className={cn("text-sm", group.isCore && "font-semibold")}>
              {group.name}
            </h2>
            {group.summary && (
              <Markdown
                variant="inline"
                className="mt-0.5 text-xs text-muted-foreground"
              >
                {group.summary}
              </Markdown>
            )}
          </div>
          <TooltipLabel label={label}>
            <button
              type="button"
              aria-label={label}
              aria-expanded={open}
              aria-controls={contentId}
              onClick={() => setOpen((value) => !value)}
              className="-my-1 flex size-7 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted"
            >
              <Icon aria-hidden className="size-3.5" />
            </button>
          </TooltipLabel>
        </div>
        {open && (
          <div id={contentId} className="mt-2">
            {group.questions.length > 0 && (
              <ul className="space-y-2">
                {group.questions.map((item, index) => (
                  <li key={index}>
                    <StudyMemoCard
                      kind="question"
                      title={item.question}
                      body={item.answer}
                    />
                  </li>
                ))}
              </ul>
            )}
            {group.terms.length > 0 && (
              <>
                <h3
                  className={cn(
                    "mb-2 text-2xs tracking-wider text-muted-foreground",
                    group.questions.length > 0 && "mt-3.5",
                  )}
                >
                  用語
                </h3>
                <ul className="space-y-2">
                  {group.terms.map((entry, index) => (
                    <li key={index}>
                      <StudyMemoCard
                        kind="term"
                        title={entry.term}
                        subtitle={entry.reading}
                        body={entry.meaning}
                      />
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
      </div>
    </li>
  );
}
