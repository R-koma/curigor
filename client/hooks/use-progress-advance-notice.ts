import { useEffect, useRef, useState } from "react";
import type { LearningProgress } from "@/hooks/use-chat-websocket";
import {
  detectAdvance,
  formatAdvance,
  type ProgressAspect,
} from "@/lib/progress";

export function useProgressAdvanceNotice(
  progress: LearningProgress | null,
  durationMs = 4000,
): string | null {
  const previous = useRef<ProgressAspect[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!progress) {
      previous.current = null;
      return;
    }
    const aspects = progress.aspects ?? [];
    const advance = detectAdvance(previous.current, aspects);
    previous.current = aspects;
    if (advance) setNotice(formatAdvance(advance));
  }, [progress]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), durationMs);
    return () => clearTimeout(timer);
  }, [notice, durationMs]);

  return notice;
}
