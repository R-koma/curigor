"use client";

import { cn } from "@/lib/utils";

const OPTIONS = [
  {
    explore: false,
    label: "説明して学ぶ",
    description: "知っていることを説明すると、AI が深掘りします",
  },
  {
    explore: true,
    label: "教わってから始める",
    description: "初めてのことを、AI に一から教わります",
  },
] as const;

export function StartModeToggle({
  explore,
  onChange,
  disabled = false,
}: {
  explore: boolean;
  onChange: (explore: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="学び方"
      className="mb-3 grid gap-2 sm:grid-cols-2"
    >
      {OPTIONS.map((option) => {
        const selected = option.explore === explore;
        return (
          <button
            key={option.label}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange(option.explore)}
            className={cn(
              "flex cursor-pointer flex-col gap-0.5 rounded-xl border px-3 py-2 text-left transition-colors",
              selected ? "border-brand bg-brand-soft" : "hover:bg-muted",
            )}
          >
            <span className="text-sm font-medium">{option.label}</span>
            <span className="text-xs text-muted-foreground">
              {option.description}
            </span>
          </button>
        );
      })}
    </div>
  );
}
