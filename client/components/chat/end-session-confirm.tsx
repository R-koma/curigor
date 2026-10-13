"use client";

import { useRef } from "react";
import { Button } from "@/components/ui/button";

type SessionKind = "learning" | "review" | "explore";

const END_LABEL: Record<SessionKind, Record<"create" | "skip", string>> = {
  learning: { create: "ノートを作成して終了", skip: "ノートを作らずに終了" },
  review: { create: "ノートを更新して終了", skip: "更新せずに終了" },
  explore: { create: "学習メモを作成して終了", skip: "学習メモを作らずに終了" },
};

const SKIP_REASON: Record<SessionKind, string> = {
  learning: "まだ説明が無いため、終了してもノートは作成されません",
  review: "まだ返答が無いため、終了してもノートは更新されません",
  explore: "まだ教わった内容が無いため、終了しても学習メモは作成されません",
};

const PROGRESS_LABEL: Record<SessionKind, string> = {
  learning: "説明できた観点",
  review: "説明できた観点",
  explore: "教わった観点",
};

interface EndSessionConfirmProps {
  kind: SessionKind;
  createsNote: boolean;
  progress?: { reached: number; target: number } | null;
  disabled?: boolean;
  onEnd: () => boolean | void;
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
    if (onEnd() !== false) endedRef.current = true;
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
            {`${PROGRESS_LABEL[kind]} ${progress.reached}/${progress.target}`}
          </span>
        )}
      </div>
    </div>
  );
}
