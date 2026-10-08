"use client";

import { InfoIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TooltipLabel } from "@/components/ui/tooltip";
import { useUsageHints } from "@/context/usage-hints-context";
import { HINT_TEXT, type HintId } from "@/lib/hints";
import { cn } from "@/lib/utils";

export function UsageHint({
  id,
  className,
}: {
  id: HintId;
  className?: string;
}) {
  const { isVisible, dismiss } = useUsageHints();
  if (!isVisible(id)) return null;

  return (
    <aside
      aria-label="使い方のヒント"
      onKeyDown={(e) => {
        if (e.key !== "Escape") return;
        e.stopPropagation();
        dismiss(id);
      }}
      className={cn(
        "flex items-start gap-2 rounded-lg border border-brand/30 bg-brand-soft px-3 py-2 text-sm text-foreground",
        className,
      )}
    >
      <InfoIcon
        aria-hidden
        className="mt-0.5 size-4 shrink-0 text-brand-text"
      />
      <p className="min-w-0 flex-1 leading-relaxed">{HINT_TEXT[id]}</p>
      <TooltipLabel label="ヒントを閉じる">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="ヒントを閉じる"
          className="-my-1 -mr-1 shrink-0 text-muted-foreground hover:text-foreground"
          onClick={() => dismiss(id)}
        >
          <XIcon className="size-4" />
        </Button>
      </TooltipLabel>
    </aside>
  );
}
