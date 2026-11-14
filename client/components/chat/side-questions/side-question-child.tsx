"use client";

import { CornerDownRightIcon } from "lucide-react";
import { childrenOf } from "@/lib/side-question-tree";
import type { SideQuestion } from "@/lib/side-questions";
import {
  ChildRows,
  FoldButton,
  SideConversation,
  firstQuestion,
  type SideThreadView,
} from "@/components/chat/side-questions/side-question-card";

export function SideQuestionChild({
  thread,
  view,
}: {
  thread: SideQuestion;
  view: SideThreadView;
}) {
  const hover = {
    onMouseEnter: () => view.onHover(thread.id),
    onMouseLeave: () => view.onHover(null),
  };

  if (!view.open.has(thread.id)) {
    return (
      <div className="flex flex-col gap-0.5">
        <button
          type="button"
          aria-expanded={false}
          onClick={() => view.onToggle(thread.id)}
          {...hover}
          className="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <CornerDownRightIcon aria-hidden className="size-3.5 shrink-0" />
          <span className="truncate">
            {firstQuestion(thread) || thread.quote}
          </span>
        </button>
        <ChildRows view={view} items={childrenOf(view.threads, thread.id)} />
      </div>
    );
  }

  return (
    <div data-side-card={thread.id} className="flex flex-col gap-2.5 py-1 pl-2">
      <div {...hover} className="flex items-center gap-1.5">
        <CornerDownRightIcon
          aria-hidden
          className="size-3.5 shrink-0 text-brand-text"
        />
        <p className="flex-1 text-xs leading-relaxed text-brand-text">
          {thread.quote}
        </p>
        <FoldButton onClick={() => view.onToggle(thread.id)} />
      </div>
      <SideConversation thread={thread} view={view} />
    </div>
  );
}
