"use client";

import { Button } from "@/components/ui/button";

interface StartQuestionsButtonProps {
  count: number;
  onStart: () => boolean | void;
}

export function StartQuestionsButton({
  count,
  onStart,
}: StartQuestionsButtonProps) {
  return (
    <div className="mt-3">
      <Button variant="outline" onClick={() => onStart()}>
        {`質問を聞く（${count}）`}
      </Button>
    </div>
  );
}
