"use client";

import { SquareIcon, Volume2Icon } from "lucide-react";
import { cn } from "@/lib/utils";

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
    <button
      type="button"
      onClick={speaking ? onStop : onPlay}
      aria-label={label}
      title={label}
      className={cn(
        "mt-2 cursor-pointer transition-opacity focus-visible:opacity-100",
        speaking ? "opacity-100" : "opacity-0 group-hover:opacity-100",
      )}
    >
      {speaking ? (
        <SquareIcon className="h-4 w-4 text-blue-600" />
      ) : (
        <Volume2Icon className="h-4 w-4 text-muted-foreground hover:text-foreground" />
      )}
    </button>
  );
}
