"use client";

import { useRef } from "react";
import { Button } from "@/components/ui/button";

type SessionKind = "learning" | "review";

const END_LABEL: Record<SessionKind, Record<"create" | "skip", string>> = {
  learning: { create: "ノートを作成して終了", skip: "ノートを作らずに終了" },
  review: { create: "ノートを更新して終了", skip: "更新せずに終了" },
};

const SKIP_REASON: Record<SessionKind, string> = {
  learning: "まだ説明が無いため、終了してもノートは作成されません",
  review: "まだ返答が無いため、終了してもノートは更新されません",
};

interface EndSessionConfirmProps {
  kind: SessionKind;
  createsNote: boolean;
  progress?: { reached: number; target: number } | null;
  disabled?: boolean;
  onEnd: () => void;
  onContinue: () => void;
}

export function EndSessionConfirm({
  kind,
  createsNote,
  progress = null,
  disabled = false,
  onEnd,
  onContinue,
}: EndSessionConfirmProps) {
  const endedRef = useRef(false);
  const end = () => {
    if (endedRef.current) return;
    endedRef.current = true;
    onEnd();
  };

  return (
    <div className="mt-3 space-y-2">
      {!createsNote && (
        <p className="text-sm text-muted-foreground">{SKIP_REASON[kind]}</p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="brand" disabled={disabled} onClick={end}>
          {END_LABEL[kind][createsNote ? "create" : "skip"]}
        </Button>
        <Button variant="outline" disabled={disabled} onClick={onContinue}>
          続ける
        </Button>
        {progress && (
          <span className="text-sm text-muted-foreground">
            説明できた観点 {progress.reached}/{progress.target}
          </span>
        )}
      </div>
    </div>
  );
}
