"use client";

import { Spinner } from "@/components/ui/spinner";
import type { VoiceStatus } from "@/hooks/use-voice-recorder";

const MESSAGES: Partial<Record<VoiceStatus, string>> = {
  starting: "マイクの許可を待っています…",
  transcribing: "文字起こし中…",
};

export function VoiceStatusRow({ status }: { status: VoiceStatus }) {
  const message = MESSAGES[status];

  return (
    <div
      role="status"
      className="flex items-center gap-2 px-3 text-xs text-muted-foreground"
    >
      {message && (
        <>
          <Spinner size="sm" />
          {message}
        </>
      )}
    </div>
  );
}
