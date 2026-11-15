"use client";

import { MessageCircleQuestionIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export function AskSideButton({
  onClick,
  disabled,
}: {
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      disabled={disabled}
      onClick={onClick}
      className="hidden h-8 rounded-full px-2.5 text-muted-foreground md:inline-flex"
    >
      <MessageCircleQuestionIcon aria-hidden className="size-4" />
      横で質問
    </Button>
  );
}
