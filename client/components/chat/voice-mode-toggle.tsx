"use client";

import { SquareIcon, Volume2Icon, VolumeXIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface VoiceModeToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  error: string | null;
  speaking?: boolean;
  onStop?: () => void;
}

export function VoiceModeToggle({
  enabled,
  onChange,
  error,
  speaking = false,
  onStop,
}: VoiceModeToggleProps) {
  const Icon = enabled ? Volume2Icon : VolumeXIcon;
  return (
    <div className="flex items-center justify-end gap-3 pb-2 text-xs">
      {error && <span className="text-destructive">{error}</span>}
      {speaking && onStop && (
        <button
          type="button"
          onClick={onStop}
          aria-label="読み上げを停止"
          className="flex cursor-pointer items-center gap-1 rounded-full bg-muted px-3 py-1 font-medium text-foreground hover:bg-muted/70"
        >
          <SquareIcon className="h-3 w-3" />
          停止
        </button>
      )}
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        aria-label="音声モード"
        onClick={() => onChange(!enabled)}
        className={cn(
          "flex cursor-pointer items-center gap-1.5 rounded-full px-3 py-1 font-medium transition-colors",
          enabled
            ? "bg-blue-600 text-white"
            : "bg-muted text-muted-foreground hover:text-foreground",
        )}
      >
        <Icon className="h-3.5 w-3.5" />
        音声モード
      </button>
    </div>
  );
}
