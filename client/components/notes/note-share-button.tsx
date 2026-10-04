"use client";

import { useState } from "react";
import { CheckIcon, CopyIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { buildNoteMarkdown } from "@/lib/note-markdown";

interface NoteShareButtonProps {
  topic: string;
  summary: string;
  content: string;
}

const COPIED_RESET_MS = 2000;

export function NoteShareButton({
  topic,
  summary,
  content,
}: NoteShareButtonProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    const markdown = buildNoteMarkdown({ topic, summary, content });
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      toast.success("Markdown をコピーしました");
      setTimeout(() => setCopied(false), COPIED_RESET_MS);
    } catch {
      toast.error("コピーできませんでした。このブラウザでは利用できません");
    }
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="icon-lg"
            onClick={handleCopy}
            aria-label="ノートをコピー"
          >
            {copied ? (
              <CheckIcon className="h-4 w-4" />
            ) : (
              <CopyIcon className="h-4 w-4" />
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>ノートをコピー</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
