"use client";

import { useId, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Markdown } from "@/components/ui/markdown";
import { TooltipLabel } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const LABEL_NOUN = { question: "答え", term: "意味" } as const;

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
  const label = `${LABEL_NOUN[kind]}を${open ? "閉じる" : "開く"}`;
  const Icon = open ? ChevronUp : ChevronDown;

  return (
    <div className="rounded-xl border bg-card">
      <div className="flex items-center justify-between gap-3 py-2.5 pr-3 pl-3.5">
        <p className="min-w-0 text-sm">
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
        </p>
        <TooltipLabel label={label}>
          <button
            type="button"
            aria-label={label}
            aria-expanded={open}
            aria-controls={bodyId}
            onClick={() => setOpen((value) => !value)}
            className={cn(
              "flex size-7 shrink-0 items-center justify-center rounded-full transition-colors",
              open
                ? "bg-brand-soft text-brand"
                : "text-muted-foreground hover:bg-muted",
            )}
          >
            <Icon aria-hidden className="size-3.5" />
          </button>
        </TooltipLabel>
      </div>
      {open && (
        <div
          id={bodyId}
          className={cn(
            "border-t pt-2.5 pr-3.5 pb-3 text-sm text-muted-foreground",
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
