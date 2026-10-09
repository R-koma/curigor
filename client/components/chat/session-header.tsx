"use client";

import Link from "next/link";
import { ArrowLeftIcon } from "lucide-react";
import type { ReactNode } from "react";
import { EndSessionButton } from "@/components/chat/end-session-button";
import {
  LearningProgressIndicator,
  ProgressAdvanceNotice,
} from "@/components/chat/learning-progress";
import { NavbarTopic } from "@/components/chat/navbar-topic";
import { ReconnectingIndicator } from "@/components/chat/reconnecting-indicator";
import { TooltipLabel } from "@/components/ui/tooltip";
import type { LearningProgress } from "@/hooks/use-chat-websocket";

interface SessionHeaderProps {
  topic: string;
  onEditTopic?: (topic: string) => boolean;
  leading?: ReactNode;
  badge?: ReactNode;
  progress?: LearningProgress | null;
  progressHighlighted?: boolean;
  progressOpen?: boolean;
  onProgressOpenChange?: (open: boolean) => void;
  notice?: string | null;
  isReconnecting?: boolean;
  endLabel: string;
  endHighlighted?: boolean;
  onEnd: () => void;
}

export function SessionHeader({
  topic,
  onEditTopic,
  leading,
  badge,
  progress,
  progressHighlighted = false,
  progressOpen,
  onProgressOpenChange,
  notice = null,
  isReconnecting = false,
  endLabel,
  endHighlighted = false,
  onEnd,
}: SessionHeaderProps) {
  return (
    <div className="flex w-full min-w-0 items-center gap-2 md:w-auto md:gap-3">
      <TooltipLabel label="ダッシュボードへ戻る">
        <Link
          href="/dashboard"
          aria-label="ダッシュボードへ戻る"
          className="-ml-2 flex size-11 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:text-foreground md:hidden"
        >
          <ArrowLeftIcon className="size-5" />
        </Link>
      </TooltipLabel>
      <div className="flex min-w-0 flex-1 items-center gap-2 md:flex-none">
        {leading}
        <NavbarTopic topic={topic} onEdit={onEditTopic} />
        {badge}
      </div>
      <div className="hidden h-4 w-px bg-border md:block" />
      {progress && (
        <LearningProgressIndicator
          progress={progress}
          highlighted={progressHighlighted}
          open={progressOpen}
          onOpenChange={onProgressOpenChange}
        />
      )}
      <div
        data-testid="session-status"
        className="absolute top-full left-4 z-raised mt-1 flex flex-col items-start gap-1 md:static md:mt-0 md:flex-row md:items-center md:gap-3"
      >
        {progress && <ProgressAdvanceNotice notice={notice} />}
        {isReconnecting && <ReconnectingIndicator />}
      </div>
      <EndSessionButton
        label={endLabel}
        highlighted={endHighlighted}
        compact
        onClick={onEnd}
      />
    </div>
  );
}
