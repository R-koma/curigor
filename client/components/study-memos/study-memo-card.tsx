"use client";

import { useId, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Markdown } from "@/components/ui/markdown";
import { cn } from "@/lib/utils";

export function StudyMemoCard({
  kind,
  title,
  subtitle,
  body,
}: {
  kind: "question" | "term";
  title: string;
  subtitle?: string;
  body: string;
}) {
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  const Icon = open ? ChevronUp : ChevronDown;

  return (
    <div className="rounded-xl border bg-card">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={open ? bodyId : undefined}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 rounded-xl py-2.5 pr-3 pl-3.5 text-left transition-colors hover:bg-muted/50"
      >
        <span className="min-w-0 text-sm">
          {kind === "question" && (
            <span aria-hidden className="mr-2.5 font-extrabold text-brand">
              Q
            </span>
          )}
          <span className="font-semibold">{title}</span>
          {subtitle && (
            <span className="ml-1.5 text-xs text-muted-foreground">
              {subtitle}
            </span>
          )}
        </span>
        <span
          aria-hidden
          className={cn(
            "flex size-7 shrink-0 items-center justify-center",
            open ? "text-brand" : "text-muted-foreground",
          )}
        >
          <Icon className="size-3.5" />
        </span>
      </button>
      {open && (
        <div
          id={bodyId}
          className={cn(
            "border-t pt-2.5 pr-3.5 pb-3 text-sm text-foreground/80",
            kind === "question" ? "pl-9.5" : "pl-3.5",
          )}
        >
          {body ? (
            <Markdown variant="inline">{body}</Markdown>
          ) : (
            <p>回答の要約はありません</p>
          )}
        </div>
      )}
    </div>
  );
}
