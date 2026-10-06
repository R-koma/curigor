"use client";

import { Button } from "@/components/ui/button";
import { useRef, useState, type KeyboardEvent } from "react";
import { CheckIcon } from "lucide-react";
import {
  ALL_SKIPPED_TEXT,
  formatIntakeAnswers,
  initialSelections,
  isAnswered,
  otherMaxLength,
  toIntakeAnswers,
  toggleOption,
  type IntakeAnswers,
  type IntakeCard,
  type IntakeQuestion,
  type IntakeSelections,
  type QuestionSelection,
} from "@/lib/intake";
import { cn } from "@/lib/utils";

interface IntakeCardViewProps {
  card: IntakeCard;
  disabled?: boolean;
  onSubmit: (content: string, answers: IntakeAnswers) => void;
}

const rowClass = (active: boolean, focused: boolean) =>
  cn(
    "flex w-full cursor-pointer items-start gap-3 rounded-xl border px-3 py-2 text-left transition-colors",
    active ? "border-brand bg-brand-soft" : "border-transparent hover:bg-muted",
    focused && "ring-2 ring-brand/40",
  );

const tabClass = (selected: boolean) =>
  cn(
    "flex cursor-pointer items-center gap-1 rounded-full px-3 py-1 text-xs font-medium transition-colors",
    selected
      ? "bg-brand text-brand-foreground"
      : "bg-muted text-muted-foreground hover:text-foreground",
  );

export function IntakeCardView({
  card,
  disabled = false,
  onSubmit,
}: IntakeCardViewProps) {
  const [selections, setSelections] = useState<IntakeSelections>(() =>
    initialSelections(card),
  );
  const [tab, setTab] = useState(0);
  const [focusedRow, setFocusedRow] = useState(0);
  const otherInputRef = useRef<HTMLInputElement>(null);
  const submittedRef = useRef(false);

  const confirmTab = card.questions.length;
  const question: IntakeQuestion | undefined = card.questions[tab];
  const selection = question ? selections[question.key] : undefined;
  const hasOptions = question ? question.options.length > 0 : true;
  const otherRow = question && hasOptions ? question.options.length : -1;
  const skipRow = otherRow + 1;

  const goTo = (next: number) => {
    setTab(Math.max(0, Math.min(next, confirmTab)));
    setFocusedRow(0);
  };
  const update = (s: QuestionSelection) => {
    if (!question) return;
    setSelections((prev) => ({ ...prev, [question.key]: s }));
  };
  const choose = (label: string) => {
    if (disabled || !question || !selection) return;
    update(toggleOption(question, selection, label));
    if (!question.multi_select) goTo(tab + 1);
  };
  const chooseOther = () => {
    if (disabled || !question || !selection) return;
    update({
      ...selection,
      otherActive: true,
      skipped: false,
      selected: question.multi_select ? selection.selected : [],
    });
    requestAnimationFrame(() => otherInputRef.current?.focus());
  };
  const skip = () => {
    if (disabled || !selection) return;
    update({ ...selection, skipped: true });
    goTo(tab + 1);
  };
  const activateRow = (row: number) => {
    if (!question) return;
    if (row < otherRow) choose(question.options[row].label);
    else if (row === otherRow) chooseOther();
    else skip();
  };
  const submit = () => {
    if (disabled || submittedRef.current) return;
    submittedRef.current = true;
    const answers = toIntakeAnswers(card, selections);
    onSubmit(formatIntakeAnswers(card, answers), answers);
  };
  const skipAll = () => {
    if (disabled || submittedRef.current) return;
    submittedRef.current = true;
    onSubmit(ALL_SKIPPED_TEXT, {
      topic: "",
      purpose: "",
      source: [],
      prior_knowledge: "",
    });
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (disabled || e.target instanceof HTMLInputElement) return;
    const isActivate = e.key === "Enter" || e.key === " ";
    if (isActivate && e.target instanceof HTMLButtonElement) return;
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      goTo(tab + (e.key === "ArrowLeft" ? -1 : 1));
      return;
    }
    if (!question) {
      if (e.key === "Enter") {
        e.preventDefault();
        submit();
      }
      return;
    }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setFocusedRow((r) =>
        Math.max(0, Math.min(r + (e.key === "ArrowDown" ? 1 : -1), skipRow)),
      );
      return;
    }
    if (isActivate) {
      e.preventDefault();
      activateRow(focusedRow);
      return;
    }
    const n = Number(e.key);
    if (Number.isInteger(n) && n >= 1 && n <= question.options.length) {
      e.preventDefault();
      choose(question.options[n - 1].label);
    }
  };

  return (
    <div
      onKeyDown={handleKeyDown}
      className={cn(
        "mt-3 rounded-2xl border bg-background p-4",
        disabled && "pointer-events-none opacity-60",
      )}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div role="tablist" className="flex flex-wrap gap-1.5">
          {card.questions.map((q, i) => {
            const answered = isAnswered(q.key, selections[q.key]);
            return (
              <button
                key={q.key}
                type="button"
                role="tab"
                aria-selected={tab === i}
                data-answered={answered}
                disabled={disabled}
                onClick={() => goTo(i)}
                className={tabClass(tab === i)}
              >
                {answered && <CheckIcon className="size-3" aria-hidden />}
                {q.header}
              </button>
            );
          })}
          <button
            type="button"
            role="tab"
            aria-selected={tab === confirmTab}
            disabled={disabled}
            onClick={() => goTo(confirmTab)}
            className={tabClass(tab === confirmTab)}
          >
            確認
          </button>
        </div>
        <button
          type="button"
          onClick={skipAll}
          disabled={disabled}
          className="shrink-0 cursor-pointer text-xs text-muted-foreground hover:text-foreground"
        >
          すべてスキップして始める
        </button>
      </div>

      {question && selection ? (
        <div>
          <p className="mb-2 text-sm font-medium">{question.question}</p>
          <div
            {...(hasOptions
              ? {
                  role: question.multi_select ? "group" : "radiogroup",
                  "aria-label": question.header,
                  tabIndex: 0,
                }
              : {})}
            className="space-y-1 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
          >
            {question.options.map((option, i) => {
              const checked = selection.selected.includes(option.label);
              return (
                <button
                  key={option.label}
                  type="button"
                  tabIndex={-1}
                  role={question.multi_select ? "checkbox" : "radio"}
                  aria-checked={checked}
                  disabled={disabled}
                  onClick={() => choose(option.label)}
                  className={rowClass(checked, focusedRow === i)}
                >
                  <span className="w-4 shrink-0 text-xs leading-5 text-muted-foreground">
                    {i + 1}.
                  </span>
                  <span className="flex min-w-0 flex-col">
                    <span className="text-sm break-words">{option.label}</span>
                    {option.description && (
                      <span className="text-xs text-muted-foreground">
                        {option.description}
                      </span>
                    )}
                  </span>
                </button>
              );
            })}
            {hasOptions && (
              <button
                type="button"
                tabIndex={-1}
                role={question.multi_select ? "checkbox" : "radio"}
                aria-checked={selection.otherActive}
                disabled={disabled}
                onClick={chooseOther}
                className={rowClass(
                  selection.otherActive,
                  focusedRow === otherRow,
                )}
              >
                <span className="w-4 shrink-0" />
                <span className="text-sm">その他（自由入力）</span>
              </button>
            )}
            {selection.otherActive && (
              <input
                ref={otherInputRef}
                type="text"
                value={selection.other}
                maxLength={otherMaxLength(question.key)}
                disabled={disabled}
                aria-label={question.header}
                placeholder="自由に入力"
                onChange={(e) =>
                  update({ ...selection, other: e.target.value })
                }
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    goTo(tab + 1);
                  }
                }}
                className={cn(
                  "rounded-lg border bg-background px-3 py-1.5 text-sm outline-none focus-visible:border-brand/60",
                  hasOptions ? "ml-7 w-[calc(100%-1.75rem)]" : "w-full",
                )}
              />
            )}
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              onClick={skip}
              disabled={disabled}
              className={cn(
                "cursor-pointer rounded-lg px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted",
                focusedRow === skipRow && "ring-2 ring-brand/40",
              )}
            >
              スキップ
            </button>
            {question.multi_select && (
              <Button
                type="button"
                variant="brand"
                size="sm"
                onClick={() => goTo(tab + 1)}
                disabled={disabled}
              >
                次へ
              </Button>
            )}
          </div>
        </div>
      ) : (
        <div>
          <p className="mb-2 text-sm font-medium">この内容で始めます</p>
          <p className="whitespace-pre-line rounded-xl bg-muted px-3 py-2 text-sm">
            {formatIntakeAnswers(card, toIntakeAnswers(card, selections))}
          </p>
          <div className="mt-3 flex justify-end">
            <Button
              type="button"
              variant="brand"
              onClick={submit}
              disabled={disabled}
            >
              送信
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
