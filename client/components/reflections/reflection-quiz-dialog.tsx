"use client";

import { useEffect, useState } from "react";
import { CheckIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { REFLECTION_LIMIT_MESSAGE } from "@/components/reflections/reflection-audio";
import { ApiError, fetchAPI } from "@/lib/api";
import type { ReflectionPeriod } from "@/lib/reflection";
import { cn } from "@/lib/utils";

interface QuizQuestion {
  question: string;
  choices: string[];
  answer_index: number;
  explanation: string;
}

const QUIZ_FAILED_MESSAGE = "小テストを作れませんでした";

function quizErrorMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 429) {
    return REFLECTION_LIMIT_MESSAGE;
  }
  return QUIZ_FAILED_MESSAGE;
}

interface ReflectionQuizDialogProps {
  period: ReflectionPeriod;
  start: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ReflectionQuizDialog({
  period,
  start,
  open,
  onOpenChange,
}: ReflectionQuizDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-md:inset-0 max-md:h-dvh max-md:max-w-none max-md:translate-x-0 max-md:translate-y-0 max-md:rounded-none max-md:overflow-y-auto md:max-h-[90dvh] md:max-w-lg md:overflow-y-auto">
        <DialogHeader>
          <DialogTitle>小テスト</DialogTitle>
          <DialogDescription>
            振り返りの内容から作った問題です。結果は保存されません。
          </DialogDescription>
        </DialogHeader>
        <QuizBody
          period={period}
          start={start}
          onClose={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  );
}

interface QuizBodyProps {
  period: ReflectionPeriod;
  start: string;
  onClose: () => void;
}

function QuizBody({ period, start, onClose }: QuizBodyProps) {
  const [questions, setQuestions] = useState<QuizQuestion[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryable, setRetryable] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [correct, setCorrect] = useState(0);

  useEffect(() => {
    let current = true;
    fetchAPI<{ questions: QuizQuestion[] }>(
      `/api/reflections/${period}/${start}/quiz`,
      { method: "POST" },
    )
      .then((res) => {
        if (current) setQuestions(res.questions);
      })
      .catch((err: unknown) => {
        if (!current) return;
        setError(quizErrorMessage(err));
        setRetryable(!(err instanceof ApiError && err.status === 429));
      });
    return () => {
      current = false;
    };
  }, [period, start, attempt]);

  const retry = () => {
    setError(null);
    setAttempt((n) => n + 1);
  };

  if (error) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p role="alert" className="text-sm text-muted-foreground">
          {error}
        </p>
        <DialogFooter className="max-md:flex-row">
          {retryable && (
            <Button variant="outline" size="sm" onClick={retry}>
              もう一度試す
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={onClose}>
            閉じる
          </Button>
        </DialogFooter>
      </div>
    );
  }

  if (!questions) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
        <Spinner size="sm" label="小テストを作成中" />
        小テストを作成中
      </div>
    );
  }

  if (index >= questions.length) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-base font-medium">
          {questions.length}問中{correct}問正解
        </p>
        <DialogFooter>
          <Button onClick={onClose}>閉じる</Button>
        </DialogFooter>
      </div>
    );
  }

  const q = questions[index];
  const answered = picked !== null;
  const isLast = index === questions.length - 1;

  const choose = (i: number) => {
    if (answered) return;
    setPicked(i);
    if (i === q.answer_index) setCorrect((n) => n + 1);
  };

  const next = () => {
    setPicked(null);
    setIndex((n) => n + 1);
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-muted-foreground">
        {index + 1} / {questions.length}
      </p>
      <p className="text-sm font-medium">{q.question}</p>
      <ul className="flex flex-col gap-2">
        {q.choices.map((choice, i) => {
          const isAnswer = answered && i === q.answer_index;
          const isWrongPick = answered && i === picked && i !== q.answer_index;
          return (
            <li key={i}>
              <button
                type="button"
                disabled={answered}
                onClick={() => choose(i)}
                className={cn(
                  "flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors enabled:hover:bg-muted disabled:cursor-default",
                  isAnswer && "border-success bg-success-soft",
                  isWrongPick && "border-destructive",
                )}
              >
                <span>{choice}</span>
                {isAnswer && (
                  <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-success-text">
                    <CheckIcon className="size-3.5" aria-hidden />
                    正解
                  </span>
                )}
                {isWrongPick && (
                  <span className="shrink-0 text-xs font-medium text-destructive">
                    不正解
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
      {answered && (
        <p className="rounded-lg bg-muted px-3 py-2 text-sm">{q.explanation}</p>
      )}
      {answered && (
        <DialogFooter>
          <Button onClick={next}>{isLast ? "結果を見る" : "次の問題"}</Button>
        </DialogFooter>
      )}
    </div>
  );
}
