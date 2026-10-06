"use client";

import { useState } from "react";
import { CheckIcon, CopyIcon } from "lucide-react";

import { MessageActionButton } from "@/components/chat/message-action-button";

interface MessageCopyButtonProps {
  content: string;
}

const COPIED_RESET_MS = 2000;

export function MessageCopyButton({ content }: MessageCopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), COPIED_RESET_MS);
    } catch {
      // クリップボード非対応環境では何もしない（コピーは付加的機能のため）
    }
  };

  return (
    <MessageActionButton label="メッセージをコピー" onClick={handleCopy}>
      {copied ? (
        <CheckIcon className="size-4 text-muted-foreground" />
      ) : (
        <CopyIcon className="size-4 text-muted-foreground hover:text-foreground" />
      )}
    </MessageActionButton>
  );
}
