"use client";

import { Button } from "@/components/ui/button";

interface StartQuestionsButtonProps {
  count: number;
  disabled?: boolean;
  onStart: () => boolean | void;
}

export function StartQuestionsButton({
  count,
  disabled = false,
  onStart,
}: StartQuestionsButtonProps) {
  return (
    <div className="mt-3">
      <Button variant="outline" disabled={disabled} onClick={() => onStart()}>
        {`質問を聞く（${count}）`}
      </Button>
    </div>
  );
}
