"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { fetchAPI } from "@/lib/api";

interface NoteEditFormProps {
  noteId: string;
  initialTopic: string;
  initialSummary: string;
  initialContent: string;
}

export function NoteEditForm({
  noteId,
  initialTopic,
  initialSummary,
  initialContent,
}: NoteEditFormProps) {
  const router = useRouter();
  const [topic, setTopic] = useState(initialTopic);
  const [summary, setSummary] = useState(initialSummary);
  const [content, setContent] = useState(initialContent);
  const [isSaving, setIsSaving] = useState(false);

  const closeEditor = () => {
    router.push(`/notes/${noteId}`);
  };

  const handleSave = async () => {
    const trimmedTopic = topic.trim();
    if (!trimmedTopic || !content.trim()) {
      toast.error("トピックと内容は必須です");
      return;
    }
    setIsSaving(true);
    try {
      await fetchAPI(`/api/notes/${noteId}`, {
        method: "PATCH",
        body: JSON.stringify({
          topic: trimmedTopic,
          summary,
          content,
        }),
      });
      closeEditor();
      router.refresh();
    } catch {
      toast.error("ノートを保存できませんでした。もう一度お試しください");
      setIsSaving(false);
    }
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        handleSave();
      }}
      className="space-y-6"
    >
      <div className="space-y-2">
        <Label htmlFor="note-topic">トピック</Label>
        <Input
          id="note-topic"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={isSaving}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="note-summary">要約</Label>
        <Textarea
          id="note-summary"
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          disabled={isSaving}
          rows={3}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="note-content">内容（Markdown）</Label>
        <Textarea
          id="note-content"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          disabled={isSaving}
          rows={16}
          className="font-mono text-sm"
        />
      </div>

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
