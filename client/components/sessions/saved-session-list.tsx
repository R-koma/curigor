"use client";

import Link from "next/link";
import { HistoryIcon, RotateCcwIcon, SquarePenIcon, XIcon } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageHeading } from "@/components/layout/page-heading";
import { EmptyState } from "@/components/ui/empty-state";
import { TooltipLabel } from "@/components/ui/tooltip";
import { buttonVariants } from "@/components/ui/button";
import { fetchAPI } from "@/lib/api";
import { PAGE_TITLES } from "@/lib/nav-links";
import {
  EXPIRY_WARNING_DAYS,
  daysUntilExpiry,
  savedSessionHref,
  type SavedSession,
} from "@/lib/saved-sessions";
import { SESSION_TYPE_DISPLAY } from "@/lib/status-display";
import { TONE_CLASSES } from "@/lib/tone";
import { cn } from "@/lib/utils";
import { draftKey, removeDraft } from "@/hooks/use-persisted-draft";
import { useDeferredDelete } from "@/hooks/use-deferred-delete";

const TYPE_ICON: Record<SavedSession["session_type"], LucideIcon> = {
  learning: SquarePenIcon,
  review: RotateCcwIcon,
  explore: HistoryIcon,
};

const UNTITLED = "（タイトル未設定）";

function relativeTime(iso: string, now: Date): string {
  const minutes = Math.floor(
    (now.getTime() - new Date(iso).getTime()) / 60_000,
  );
  if (minutes < 1) return "たった今";
  if (minutes < 60) return `${minutes} 分前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 時間前`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} 日前`;
  return new Date(iso).toLocaleDateString("ja-JP", {
    month: "long",
    day: "numeric",
  });
}

async function removeSession(session: SavedSession): Promise<void> {
  await fetchAPI(`/api/dialogue-sessions/${session.session_id}`, {
    method: "DELETE",
  });
  removeDraft(draftKey.session(session.session_id));
}

function SavedSessionRow({
  session,
  now,
  onDelete,
}: {
  session: SavedSession;
  now: Date;
  onDelete: () => void;
}) {
  const { label, tone } = SESSION_TYPE_DISPLAY[session.session_type];
  const classes = TONE_CLASSES[tone];
  const Icon = TYPE_ICON[session.session_type];
  const href = savedSessionHref(session);
  const topic = session.topic ?? UNTITLED;
  const expiring =
    daysUntilExpiry(session.expires_at, now) < EXPIRY_WARNING_DAYS;
  const kind = session.progress
    ? `${label} · 観点 ${session.progress.reached}/${session.progress.target}`
    : label;

  const body = (
    <>
      <div
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-[10px]",
          classes.soft,
          classes.text,
        )}
      >
        <Icon aria-hidden className="size-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="min-w-0 truncate font-medium">{topic}</span>
          <span
            className={cn(
              "shrink-0 text-xs",
              expiring ? "text-destructive" : "text-muted-foreground",
            )}
          >
            {expiring
              ? `あと ${daysUntilExpiry(session.expires_at, now)} 日で削除`
              : relativeTime(session.last_activity_at, now)}
          </span>
        </div>
        {session.last_assistant_excerpt && (
          <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
            {`AI: ${session.last_assistant_excerpt}`}
          </p>
        )}
        <p className="mt-1 text-xs text-muted-foreground">{kind}</p>
      </div>
    </>
  );

  return (
    <li className="group relative flex items-start gap-1 border-t first:border-t-0 hover:bg-muted/50">
      {href ? (
        <Link href={href} className="flex min-w-0 flex-1 gap-3 p-3.5">
          {body}
        </Link>
      ) : (
        <div className="flex min-w-0 flex-1 gap-3 p-3.5">{body}</div>
      )}
      <TooltipLabel label="削除">
        <button
          type="button"
          aria-label={`「${topic}」を削除`}
          onClick={onDelete}
          className="mr-2 mt-2 flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-opacity hover:bg-muted hover:text-foreground pointer-fine:opacity-0 pointer-fine:group-hover:opacity-100 pointer-fine:focus-visible:opacity-100 pointer-coarse:size-11"
        >
          <XIcon aria-hidden className="size-4" />
        </button>
      </TooltipLabel>
    </li>
  );
}

export function SavedSessionList({
  sessions,
  now,
}: {
  sessions: SavedSession[];
  now: Date;
}) {
  const { visible, requestDelete } = useDeferredDelete(sessions, removeSession);

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 md:px-6 md:py-8">
      <div className="mb-6">
        <PageHeading
          title={PAGE_TITLES["/sessions"]}
          description={`${visible.length} 件 · 30 日触らないと自動で消えます。保存されるのは送った会話までです`}
        />
      </div>
      {visible.length === 0 ? (
        <EmptyState
          icon={HistoryIcon}
          title="保存中の会話はありません"
          action={
            <Link href="/learn" className={buttonVariants({ size: "sm" })}>
              新しく学ぶ
            </Link>
          }
        />
      ) : (
        <ul className="overflow-hidden rounded-xl border bg-card">
          {visible.map((session) => (
            <SavedSessionRow
              key={session.session_id}
              session={session}
              now={now}
              onDelete={() => requestDelete(session, session.topic ?? UNTITLED)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
