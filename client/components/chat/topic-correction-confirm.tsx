"use client";

import { useRef } from "react";
import { Button } from "@/components/ui/button";
import type { TopicCorrectionAnswer } from "@/lib/topic-correction";

interface TopicCorrectionConfirmProps {
  disabled?: boolean;
  onAnswer: (answer: TopicCorrectionAnswer) => boolean;
}

export function TopicCorrectionConfirm({
  disabled = false,
  onAnswer,
}: TopicCorrectionConfirmProps) {
  const answeredRef = useRef(false);

  const answer = (value: TopicCorrectionAnswer) => {
    if (answeredRef.current) return;
    answeredRef.current = onAnswer(value);
  };

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      <Button
        variant="brand"
        disabled={disabled}
        onClick={() => answer("accept")}
      >
        はい、変更する
      </Button>
      <Button
        variant="outline"
        disabled={disabled}
        onClick={() => answer("decline")}
      >
        いいえ
      </Button>
    </div>
  );
}
