"use client";

import { PencilIcon } from "lucide-react";

import { MessageActionButton } from "@/components/chat/message-action-button";

interface EditResendButtonProps {
  onClick: () => void;
}

export function EditResendButton({ onClick }: EditResendButtonProps) {
  return (
    <MessageActionButton label="編集して再送信" onClick={onClick}>
      <PencilIcon className="size-4 text-muted-foreground hover:text-foreground" />
    </MessageActionButton>
  );
}
