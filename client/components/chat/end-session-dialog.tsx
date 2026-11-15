"use client";

import { useEffect, useRef, useState } from "react";
import { CirclePauseIcon, LogOutIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useIsDesktop } from "@/hooks/use-is-desktop";
import {
  DIALOG_TITLE,
  DISCARD_CONFIRM,
  DISCARD_LABEL,
  DISCARD_NO,
  DISCARD_YES,
  END_SESSION_COPY,
  END_WHEN,
  SAVE_LABEL,
  SAVE_POINT,
  SAVE_WHEN,
  type SessionKind,
} from "@/lib/end-session-copy";
import { cn } from "@/lib/utils";

interface EndSessionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  kind: SessionKind;
  topic: string;
  progress: { reached: number; target: number } | null;
  onEnd: () => boolean | void;
  onSave: () => void;
  onDiscard: () => Promise<void>;
}

function Point({ ok, children }: { ok: boolean; children: string }) {
  return (
    <li className="flex gap-2">
      <span
        data-testid="point-mark"
        className={cn(
          "w-3.5 shrink-0 text-center font-bold",
          ok ? "text-success-text" : "text-destructive",
        )}
      >
        {ok ? "✓" : "✕"}
      </span>
      <span>{children}</span>
    </li>
  );
}

function Choice({
  primary = false,
  icon,
  when,
  label,
  onClick,
  children,
}: {
  primary?: boolean;
  icon: React.ReactNode;
  when: string;
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-col items-start gap-2.5 rounded-xl border-[1.5px] p-4 text-left transition-colors",
        primary
          ? "border-brand bg-brand/10"
          : "border-border hover:border-brand/55",
      )}
    >
      <span
        className={cn(
          "flex size-8 items-center justify-center rounded-[10px]",
          primary ? "bg-brand text-white" : "bg-muted",
        )}
      >
        {icon}
      </span>
      <span className="flex flex-col">
        <span
          className={cn(
            "text-xs font-semibold",
            primary ? "text-brand" : "text-muted-foreground",
          )}
        >
          {when}
        </span>
        <span className="text-sm font-semibold">{label}</span>
      </span>
      <ul className="flex flex-col gap-1.5 text-xs">{children}</ul>
    </button>
  );
}

export function EndSessionDialog({
  open,
  onOpenChange,
  kind,
  topic,
  progress,
  onEnd,
  onSave,
  onDiscard,
}: EndSessionDialogProps) {
  const isDesktop = useIsDesktop();
  const [confirmingDiscard, setConfirmingDiscard] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const endedRef = useRef(false);
  const copy = END_SESSION_COPY[kind];

  useEffect(() => {
    if (open) endedRef.current = false;
  }, [open]);

  const handleOpenChange = (next: boolean) => {
    if (!next) setConfirmingDiscard(false);
    onOpenChange(next);
  };
  const end = () => {
    if (endedRef.current) return;
    if (onEnd() !== false) endedRef.current = true;
  };
  const discard = async () => {
    setDiscarding(true);
    try {
      await onDiscard();
    } finally {
      setDiscarding(false);
    }
  };

  const body = confirmingDiscard ? (
    <div className="space-y-4">
      <p className="text-sm">{DISCARD_CONFIRM}</p>
      <div className="flex justify-end gap-2">
        <Button
          variant="outline"
          disabled={discarding}
          onClick={() => setConfirmingDiscard(false)}
        >
          {DISCARD_NO}
        </Button>
        <Button variant="destructive" disabled={discarding} onClick={discard}>
          {DISCARD_YES}
        </Button>
      </div>
    </div>
  ) : (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <Choice
          primary
          icon={<LogOutIcon className="size-4" />}
          when={END_WHEN}
          label={copy.primary}
          onClick={end}
        >
          {copy.primaryPoints.map((p) => (
            <Point key={p} ok>
              {p}
            </Point>
          ))}
        </Choice>
        <Choice
          icon={<CirclePauseIcon className="size-4" />}
          when={SAVE_WHEN}
          label={SAVE_LABEL}
          onClick={onSave}
        >
          <Point ok>{SAVE_POINT}</Point>
          {copy.saveNots.map((p) => (
            <Point key={p} ok={false}>
              {p}
            </Point>
          ))}
        </Choice>
      </div>
      <div className="flex items-center justify-between border-t pt-3.5">
        <Button
          variant="ghost"
          size="sm"
          className="text-destructive hover:text-destructive"
          onClick={() => setConfirmingDiscard(true)}
        >
          {DISCARD_LABEL}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleOpenChange(false)}
        >
          キャンセル
        </Button>
      </div>
    </div>
  );

  const header = (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        {isDesktop ? (
          <DialogTitle className="text-lg">{DIALOG_TITLE}</DialogTitle>
        ) : (
          <SheetTitle className="text-lg">{DIALOG_TITLE}</SheetTitle>
        )}
        <p className="truncate text-sm text-muted-foreground">{topic}</p>
      </div>
      {progress && (
        <span className="shrink-0 rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground">
          {`説明できた観点 ${progress.reached} / ${progress.target}`}
        </span>
      )}
    </div>
  );

  if (isDesktop) {
    return (
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent
          className="max-w-[640px] gap-4 p-6 sm:max-w-[640px]"
          showCloseButton={false}
          aria-describedby={undefined}
        >
          {header}
          {body}
        </DialogContent>
      </Dialog>
    );
  }
  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent side="bottom" className="gap-4 overflow-y-auto px-4 pt-4">
        {header}
        {body}
      </SheetContent>
    </Sheet>
  );
}
