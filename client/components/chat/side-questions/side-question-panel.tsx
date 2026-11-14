"use client";

import { ChevronsDownUpIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TooltipLabel } from "@/components/ui/tooltip";
import { topLevelInOrder } from "@/lib/side-question-tree";
import type { SideQuestion } from "@/lib/side-questions";
import { anchorOffset } from "@/lib/text-anchor";
import { cn } from "@/lib/utils";
import {
  SideQuestionCard,
  type SideThreadView,
} from "@/components/chat/side-questions/side-question-card";

function positionInText(thread: SideQuestion): number | null {
  if (!thread.anchorMessageId || typeof document === "undefined") return null;
  const root = document.querySelector<HTMLElement>(
    `[data-message-id="${CSS.escape(thread.anchorMessageId)}"]`,
  );
  return root ? anchorOffset(root, thread.quote, thread.occurrence) : null;
}

export function SideQuestionPanel({
  view,
  messageOrder,
  overlayClosed,
  onFoldAll,
  onCloseOverlay,
}: {
  view: SideThreadView;
  messageOrder: string[];
  overlayClosed: boolean;
  onFoldAll: () => void;
  onCloseOverlay: () => void;
}) {
  const tops = topLevelInOrder(view.threads, messageOrder, positionInText);

  return (
    <aside
      aria-label="質問"
      className={cn(
        "absolute inset-y-0 right-0 z-drawer hidden w-100 max-w-full flex-col border-l bg-background shadow-lg pointer-coarse:hidden",
        "xl:static xl:z-auto xl:flex xl:shrink-0 xl:shadow-none",
        overlayClosed ? "md:hidden" : "md:flex",
      )}
    >
      <div className="flex h-13 shrink-0 items-center gap-1 pr-3 pl-6">
        <h2 className="flex flex-1 items-baseline gap-2 text-sm font-semibold">
          質問
          <span className="text-xs font-normal text-muted-foreground tabular-nums">
            {view.threads.length}
          </span>
        </h2>
        <TooltipLabel label="すべて畳む">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="すべて畳む"
            disabled={view.open.size === 0}
            onClick={onFoldAll}
            className="text-muted-foreground"
          >
            <ChevronsDownUpIcon aria-hidden className="size-4" />
          </Button>
        </TooltipLabel>
        <TooltipLabel label="閉じる">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="閉じる"
            onClick={onCloseOverlay}
            className="text-muted-foreground xl:hidden"
          >
            <XIcon aria-hidden className="size-4" />
          </Button>
        </TooltipLabel>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-3 pb-6">
        {tops.map((thread) => (
          <SideQuestionCard key={thread.id} thread={thread} view={view} />
        ))}
      </div>
    </aside>
  );
}
