"use client";

import { useState } from "react";
import { ArrowUpIcon } from "lucide-react";
import { TooltipLabel } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export function SideQuestionInput({
  hasMessages,
  disabled,
  autoFocus,
  initialValue,
  onSend,
}: {
  hasMessages: boolean;
  disabled: boolean;
  autoFocus?: boolean;
  initialValue?: string;
  onSend: (content: string) => void;
}) {
  const [value, setValue] = useState(initialValue ?? "");
  const [restored, setRestored] = useState(initialValue);
  if (initialValue !== restored) {
    setRestored(initialValue);
    if (initialValue) setValue(initialValue);
    else if (value === restored) setValue("");
  }
  const canSend = !disabled && value.trim() !== "";
  const label = hasMessages ? "続けて聞く" : "ここについて聞きたいこと";

  const submit = () => {
    if (!canSend) return;
    onSend(value.trim());
    setValue("");
  };

  return (
    <div className="flex items-center gap-1.5 rounded-full bg-muted py-1 pr-1 pl-3.5 focus-within:ring-2 focus-within:ring-brand/40">
      <input
        type="text"
        value={value}
        aria-label={label}
        placeholder={label}
        disabled={disabled}
        autoFocus={autoFocus}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key !== "Enter" || e.nativeEvent.isComposing) return;
          if (e.keyCode === 229) return;
          e.preventDefault();
          submit();
        }}
        className="h-7 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:opacity-60"
      />
      <TooltipLabel label="送信">
        <button
          type="button"
          aria-label="送信"
          disabled={!canSend}
          onClick={submit}
          className={cn(
            "grid size-7 shrink-0 place-items-center rounded-full transition-colors",
            canSend
              ? "bg-foreground text-background"
              : "text-muted-foreground opacity-60",
          )}
        >
          <ArrowUpIcon aria-hidden className="size-3.5" />
        </button>
      </TooltipLabel>
    </div>
  );
}
