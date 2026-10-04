import { useState } from "react";
import type { LearningProgress } from "@/hooks/use-chat-websocket";
import { canOpenProgressPanel } from "@/components/chat/learning-progress";

export function useProgressPanel(progress: LearningProgress | null) {
  const [open, setOpen] = useState(false);
  const canOpen = progress !== null && canOpenProgressPanel(progress);
  if (open && !canOpen) setOpen(false);
  return {
    open: open && canOpen,
    setOpen,
    openPanel: canOpen ? () => setOpen(true) : undefined,
  };
}
