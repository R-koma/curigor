"use client";

import { SquareIcon, Volume2Icon } from "lucide-react";
import { MessageActionButton } from "@/components/chat/message-action-button";

interface MessageSpeechButtonProps {
  speaking: boolean;
  onPlay: () => void;
  onStop: () => void;
}

export function MessageSpeechButton({
  speaking,
  onPlay,
  onStop,
}: MessageSpeechButtonProps) {
  const label = speaking ? "読み上げを停止" : "読み上げる";
  return (
    <MessageActionButton
      label={label}
      alwaysVisible={speaking}
      onClick={speaking ? onStop : onPlay}
    >
      {speaking ? (
        <SquareIcon className="size-4 text-brand-text" />
      ) : (
        <Volume2Icon className="size-4 text-muted-foreground hover:text-foreground" />
      )}
    </MessageActionButton>
  );
}
