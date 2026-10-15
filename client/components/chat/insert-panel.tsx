"use client";

import { useState } from "react";
import { XIcon } from "lucide-react";
import { CodeEditor } from "@/components/chat/code-editor";
import { MathEditor } from "@/components/chat/math-editor";
import { Button } from "@/components/ui/button";
import { TooltipLabel } from "@/components/ui/tooltip";
import {
  CODE_LANGUAGES,
  readStoredFence,
  storeFence,
} from "@/lib/code-languages";

export type InsertKind = "math" | "code";

interface InsertPanelProps {
  kind: InsertKind;
  initialLatex?: string;
  onInsertMath: (latex: string) => void;
  onInsertCode: (code: string, fence: string) => void;
  onClose: () => void;
  onKeyboardHeight: (height: number) => void;
}

const TITLES: Record<InsertKind, string> = { math: "数式", code: "コード" };

export function InsertPanel({
  kind,
  initialLatex = "",
  onInsertMath,
  onInsertCode,
  onClose,
  onKeyboardHeight,
}: InsertPanelProps) {
  const [content, setContent] = useState(initialLatex);
  const [fence, setFence] = useState(readStoredFence);
  const canInsert = content.trim() !== "";

  const insert = () => {
    if (!canInsert) return;
    if (kind === "math") onInsertMath(content.trim());
    else onInsertCode(content, fence);
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key !== "Escape") return;
    if ((event.target as HTMLElement).closest(".cm-editor")) return;
    event.preventDefault();
    onClose();
  };

  return (
    <div
      role="group"
      aria-label={`${TITLES[kind]}を挿入`}
      onKeyDown={handleKeyDown}
      className="mb-2 rounded-xl border bg-background p-2"
    >
      <div className="mb-2 flex items-center gap-2">
        <span className="text-sm font-medium">{TITLES[kind]}</span>
        {kind === "code" && (
          <select
            aria-label="言語"
            value={fence}
            onChange={(event) => {
              setFence(event.target.value);
              storeFence(event.target.value);
            }}
            className="rounded-md border bg-background px-2 py-1 text-sm pointer-coarse:py-2"
          >
            {CODE_LANGUAGES.map((language) => (
              <option key={language.fence} value={language.fence}>
                {language.label}
              </option>
            ))}
            <option value="">なし</option>
          </select>
        )}
        <div className="ml-auto flex items-center gap-1">
          <Button
            type="button"
            size="sm"
            onClick={insert}
            disabled={!canInsert}
            className="pointer-coarse:h-11"
          >
            挿入
          </Button>
          <TooltipLabel label="閉じる">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="閉じる"
              onClick={onClose}
              className="size-8 rounded-full pointer-coarse:size-11"
            >
              <XIcon className="size-4" />
            </Button>
          </TooltipLabel>
        </div>
      </div>
      {kind === "math" ? (
        <MathEditor
          initialValue={initialLatex}
          onChange={setContent}
          onSubmit={insert}
          onKeyboardHeight={onKeyboardHeight}
        />
      ) : (
        <CodeEditor fence={fence} onChange={setContent} onSubmit={insert} />
      )}
    </div>
  );
}
