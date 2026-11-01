"use client";

import { ChevronRightIcon, CircleHelpIcon } from "lucide-react";
import { Collapsible } from "radix-ui";
import type { ComponentProps } from "react";
import type { StudyMemoQuestion } from "@/lib/study-memos";
import { cn } from "@/lib/utils";

type StruggleAccordionProps = { topics?: string[] } & (
  | { variant: "struggle"; items: string[] }
  | { variant: "question"; items: StudyMemoQuestion[] }
);

const VARIANTS = {
  struggle: {
    label: "うまく説明できなかった所",
    icon: FilledWarningIcon,
    badge: "bg-destructive/10 text-destructive",
  },
  question: {
    label: "出た疑問",
    icon: CircleHelpIcon,
    badge: "bg-caution-soft text-caution-text",
  },
} as const;

export function StruggleAccordion(props: StruggleAccordionProps) {
  if (props.items.length === 0) return null;
  const { label, icon: Icon, badge } = VARIANTS[props.variant];

  return (
    <Collapsible.Root className="group/fold mt-1">
      <Collapsible.Trigger className="flex w-full cursor-pointer items-center gap-2 rounded-md py-1 text-left text-sm font-medium text-muted-foreground transition-colors hover:text-foreground pointer-coarse:min-h-11">
        <span
          aria-hidden
          className={cn(
            "flex size-5 shrink-0 items-center justify-center rounded-md",
            badge,
          )}
        >
          <Icon className="size-3.5" strokeWidth={2.5} />
        </span>
        {label}
        <ChevronRightIcon
          aria-hidden
          className="size-4 transition-transform group-data-[state=open]/fold:rotate-90"
        />
      </Collapsible.Trigger>
      <Collapsible.Content className="pb-2 pl-7 text-sm leading-relaxed">
        {props.variant === "struggle" ? (
          <ul className="list-disc space-y-1 pl-4 marker:text-muted-foreground">
            {props.items.map((item, i) => (
              <li key={i}>
                <TopicLabel topic={props.topics?.[i]} />
                {item}
              </li>
            ))}
          </ul>
        ) : (
          <dl className="space-y-3">
            {props.items.map((item, i) => (
              <div key={i} className="space-y-1">
                <dt className="flex gap-1.5">
                  <TopicLabel topic={props.topics?.[i]} />
                  <span className="font-semibold">Q.</span>
                  <span>{item.question}</span>
                </dt>
                {item.answer.trim() && (
                  <dd className="flex gap-1.5 text-muted-foreground">
                    <span className="font-semibold text-foreground">A.</span>
                    <span>{item.answer}</span>
                  </dd>
                )}
              </div>
            ))}
          </dl>
        )}
      </Collapsible.Content>
    </Collapsible.Root>
  );
}

function FilledWarningIcon(props: ComponentProps<"svg">) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      <rect
        x="11"
        y="8.5"
        width="2"
        height="5.5"
        rx="1"
        className="fill-card"
      />
      <circle cx="12" cy="17" r="1.2" className="fill-card" />
    </svg>
  );
}

function TopicLabel({ topic }: { topic: string | undefined }) {
  if (!topic) return null;
  return (
    <span className="mr-1.5 text-xs leading-relaxed font-semibold text-muted-foreground">
      {topic}
    </span>
  );
}
