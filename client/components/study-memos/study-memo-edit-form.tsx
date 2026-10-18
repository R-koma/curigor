"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2Icon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { TooltipLabel } from "@/components/ui/tooltip";
import { fetchAPI } from "@/lib/api";
import type {
  StudyMemo,
  StudyMemoQuestion,
  StudyMemoTerm,
} from "@/lib/study-memos";

type Indexed<T> = T & { index: number };

function indexed<T>(items: T[]): Indexed<T>[] {
  return items.map((item, index) => ({ ...item, index }));
}

function RemoveButton({
  label,
  disabled,
  onClick,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <TooltipLabel label={label}>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={label}
        disabled={disabled}
        onClick={onClick}
        className="shrink-0 text-muted-foreground hover:text-destructive"
      >
        <Trash2Icon className="size-4" />
      </Button>
    </TooltipLabel>
  );
}

export function StudyMemoEditForm({ memo }: { memo: StudyMemo }) {
  const router = useRouter();
  const [topic, setTopic] = useState(memo.topic);
  const [summary, setSummary] = useState(memo.summary);
  const [questions, setQuestions] = useState<Indexed<StudyMemoQuestion>[]>(() =>
    indexed(memo.questions),
  );
  const [glossary, setGlossary] = useState<Indexed<StudyMemoTerm>[]>(() =>
    indexed(memo.glossary),
  );
  const [isSaving, setIsSaving] = useState(false);

  const closeEditor = () => {
    router.push(`/study-memos/${memo.id}`);
  };

  const updateQuestion = (index: number, patch: Partial<StudyMemoQuestion>) => {
    setQuestions((items) =>
      items.map((item) =>
        item.index === index ? { ...item, ...patch } : item,
      ),
    );
  };

  const updateTerm = (index: number, patch: Partial<StudyMemoTerm>) => {
    setGlossary((items) =>
      items.map((item) =>
        item.index === index ? { ...item, ...patch } : item,
      ),
    );
  };

  const handleSave = async () => {
    if (!topic.trim()) {
      toast.error("トピックは必須です");
      return;
    }
    if (
      questions.some((q) => !q.question.trim()) ||
      glossary.some((t) => !t.term.trim())
    ) {
      toast.error("空の疑問・用語は削除してください");
      return;
    }
    setIsSaving(true);
    try {
      await fetchAPI(`/api/study-memos/${memo.id}`, {
        method: "PATCH",
        body: JSON.stringify({ topic, summary, questions, glossary }),
      });
      closeEditor();
      router.refresh();
    } catch {
      toast.error("学習メモを保存できませんでした。もう一度お試しください");
      setIsSaving(false);
    }
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void handleSave();
      }}
      className="mx-auto max-w-2xl space-y-8 px-4 pt-6 pb-10 md:px-6 md:pt-8"
    >
      <h1 className="text-2xl font-bold tracking-tight">学習メモを編集</h1>

      <div className="space-y-2">
        <Label htmlFor="memo-topic">トピック</Label>
        <Input
          id="memo-topic"
          value={topic}
          maxLength={60}
          onChange={(e) => setTopic(e.target.value)}
          disabled={isSaving}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="memo-summary">要約</Label>
        <Textarea
          id="memo-summary"
          value={summary}
          maxLength={1000}
          onChange={(e) => setSummary(e.target.value)}
          disabled={isSaving}
          rows={4}
          placeholder="学んだ内容の要約"
        />
      </div>

      <fieldset className="space-y-3">
        <legend className="mb-3 text-sm font-medium">疑問と回答</legend>
        {questions.length === 0 && (
          <p className="text-sm text-muted-foreground">疑問はありません</p>
        )}
        {questions.map((item, position) => (
          <div key={item.index} className="flex gap-2 rounded-xl border p-3">
            <div className="min-w-0 flex-1 space-y-2">
              <Input
                aria-label={`疑問 ${position + 1}`}
                value={item.question}
                maxLength={500}
                onChange={(e) =>
                  updateQuestion(item.index, { question: e.target.value })
                }
                disabled={isSaving}
              />
              <Textarea
                aria-label={`疑問 ${position + 1} の回答`}
                value={item.answer}
                maxLength={2000}
                onChange={(e) =>
                  updateQuestion(item.index, { answer: e.target.value })
                }
                disabled={isSaving}
                rows={3}
              />
            </div>
            <RemoveButton
              label={`疑問 ${position + 1} を削除`}
              disabled={isSaving}
              onClick={() =>
                setQuestions((items) =>
                  items.filter((q) => q.index !== item.index),
                )
              }
            />
          </div>
        ))}
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="mb-3 text-sm font-medium">用語</legend>
        {glossary.length === 0 && (
          <p className="text-sm text-muted-foreground">用語はありません</p>
        )}
        {glossary.map((item, position) => (
          <div key={item.index} className="flex gap-2 rounded-xl border p-3">
            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex gap-2">
                <Input
                  aria-label={`用語 ${position + 1}`}
                  value={item.term}
                  maxLength={60}
                  onChange={(e) =>
                    updateTerm(item.index, { term: e.target.value })
                  }
                  disabled={isSaving}
                />
                <Input
                  aria-label={`用語 ${position + 1} の読み`}
                  placeholder="読み"
                  value={item.reading}
                  maxLength={60}
                  onChange={(e) =>
                    updateTerm(item.index, { reading: e.target.value })
                  }
                  disabled={isSaving}
                />
              </div>
              <Textarea
                aria-label={`用語 ${position + 1} の意味`}
                value={item.meaning}
                maxLength={500}
                onChange={(e) =>
                  updateTerm(item.index, { meaning: e.target.value })
                }
                disabled={isSaving}
                rows={2}
              />
            </div>
            <RemoveButton
              label={`用語 ${position + 1} を削除`}
              disabled={isSaving}
              onClick={() =>
                setGlossary((items) =>
                  items.filter((t) => t.index !== item.index),
                )
              }
            />
          </div>
        ))}
      </fieldset>

      <div className="flex gap-3">
        <Button type="submit" disabled={isSaving}>
          {isSaving ? "保存中..." : "保存"}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={closeEditor}
          disabled={isSaving}
        >
          キャンセル
        </Button>
      </div>
    </form>
  );
}
