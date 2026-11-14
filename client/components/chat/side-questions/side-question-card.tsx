"use client";

import { ChevronUpIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/ui/markdown";
import { Spinner } from "@/components/ui/spinner";
import { TooltipLabel } from "@/components/ui/tooltip";
import { closeOpenBlocks } from "@/lib/chat-markdown";
import { childrenOf } from "@/lib/side-question-tree";
import { MAX_SIDE_DEPTH, type SideQuestion } from "@/lib/side-questions";
import type { SideError, SideStreaming } from "@/hooks/use-side-questions";
import { SideQuestionChild } from "@/components/chat/side-questions/side-question-child";
import { SideQuestionInput } from "@/components/chat/side-questions/side-question-input";

export interface SideThreadView {
  threads: SideQuestion[];
  open: Set<string>;
  streaming: SideStreaming | null;
  error: SideError | null;
  focusId: string | null;
  onToggle: (id: string) => void;
  onSend: (id: string, content: string) => void;
  onHover: (id: string | null) => void;
}

export function firstQuestion(thread: SideQuestion): string {
  return thread.messages.find((m) => m.role === "user")?.content ?? "";
}

export function ChildRows({
  view,
  items,
}: {
  view: SideThreadView;
  items: SideQuestion[];
}) {
  if (items.length === 0) return null;
  const active = items.some((child) => view.open.has(child.id));
  return (
    <div
      className={`flex flex-col gap-0.5 border-l-2 pl-2 transition-colors ${
        active ? "border-brand/40" : "border-border"
      }`}
    >
      {items.map((child) => (
        <SideQuestionChild key={child.id} thread={child} view={view} />
      ))}
    </div>
  );
}

export function SideConversation({
  thread,
  view,
}: {
  thread: SideQuestion;
  view: SideThreadView;
}) {
  const streaming =
    view.streaming?.sideQuestionId === thread.id ? view.streaming : null;
  const error = view.error?.id === thread.id ? view.error : null;
  const selectable = thread.depth < MAX_SIDE_DEPTH;

  return (
    <>
      {thread.messages.map((message) =>
        message.role === "user" ? (
          <p
            key={message.id}
            className="max-w-[92%] self-end rounded-2xl bg-muted px-3 py-1.5 text-sm leading-relaxed whitespace-pre-wrap"
          >
            {message.content}
          </p>
        ) : (
          <div key={message.id} className="flex flex-col gap-2">
            <div
              data-side-message-id={message.id}
              data-side-thread-id={thread.id}
              data-side-depth={thread.depth}
              data-side-selectable={selectable ? "" : undefined}
              className="text-sm leading-relaxed"
            >
              <Markdown
                variant="chat"
                className="[&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
              >
                {closeOpenBlocks(message.content, { streaming: false })}
              </Markdown>
            </div>
            <ChildRows
              view={view}
              items={childrenOf(view.threads, thread.id, message.id)}
            />
          </div>
        ),
      )}
      {streaming?.question && (
        <p className="max-w-[92%] self-end rounded-2xl bg-muted px-3 py-1.5 text-sm leading-relaxed whitespace-pre-wrap">
          {streaming.question}
        </p>
      )}
      {streaming &&
        (streaming.text ? (
          <div className="text-sm leading-relaxed">
            <Markdown
              variant="chat"
              className="[&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
            >
              {closeOpenBlocks(streaming.text, { streaming: true })}
            </Markdown>
          </div>
        ) : (
          <Spinner size="sm" label="回答を作っています" />
        ))}
      {error && (
        <div
          role="alert"
          className="flex flex-col items-start gap-1.5 text-sm text-destructive"
        >
          <p>{error.detail}</p>
          <Button
            variant="outline"
            size="xs"
            disabled={view.streaming !== null}
            onClick={() => view.onSend(thread.id, error.content)}
          >
            もう一度送る
          </Button>
        </div>
      )}
      <SideQuestionInput
        key={thread.id}
        hasMessages={thread.messages.length > 0}
        disabled={view.streaming !== null}
        autoFocus={view.focusId === thread.id}
        initialValue={error?.content}
        onSend={(content) => view.onSend(thread.id, content)}
      />
    </>
  );
}

export function SideQuestionCard({
  thread,
  view,
}: {
  thread: SideQuestion;
  view: SideThreadView;
}) {
  const isOpen = view.open.has(thread.id);
  const hover = {
    onMouseEnter: () => view.onHover(thread.id),
    onMouseLeave: () => view.onHover(null),
  };

  if (!isOpen) {
    return (
      <div className="shrink-0 overflow-hidden rounded-2xl border bg-card">
        <button
          type="button"
          aria-expanded={false}
          onClick={() => view.onToggle(thread.id)}
          {...hover}
          className="flex w-full flex-col gap-0.5 px-3.5 py-2.5 text-left transition-colors hover:bg-muted"
        >
          <span className="truncate text-sm font-medium">
            {firstQuestion(thread) || thread.quote}
          </span>
          <span className="truncate text-xs text-muted-foreground">
            {thread.quote}
          </span>
        </button>
        {childrenOf(view.threads, thread.id).length > 0 && (
          <div className="px-3 pb-2.5">
            <ChildRows
              view={view}
              items={childrenOf(view.threads, thread.id)}
            />
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      data-side-card={thread.id}
      className="shrink-0 overflow-hidden rounded-2xl border bg-card"
    >
      <div
        {...hover}
        className="flex w-full items-start gap-2.5 pt-3.5 pr-2.5 pb-1 pl-4"
      >
        <p className="flex-1 border-l-2 border-brand pl-2.5 text-xs leading-relaxed text-muted-foreground">
          {thread.quote}
        </p>
        <FoldButton onClick={() => view.onToggle(thread.id)} />
      </div>
      <div className="flex flex-col gap-3 px-4 pt-3 pb-3">
        <SideConversation thread={thread} view={view} />
      </div>
    </div>
  );
}

export function FoldButton({ onClick }: { onClick: () => void }) {
  return (
    <TooltipLabel label="畳む">
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label="畳む"
        aria-expanded
        onClick={onClick}
        className="-mt-0.5 shrink-0 text-muted-foreground"
      >
        <ChevronUpIcon aria-hidden className="size-4" />
      </Button>
    </TooltipLabel>
  );
}
