"use client";

import { useEffect, useRef } from "react";
import type { SpokenSentence } from "@/hooks/use-speech-playback";
import { findSentenceRange } from "@/lib/speech-highlight";

const HIGHLIGHT_NAME = "speaking";

function highlightRegistry(): HighlightRegistry | null {
  if (typeof CSS === "undefined" || typeof Highlight === "undefined") {
    return null;
  }
  return CSS.highlights ?? null;
}

export function useSpeakingHighlight(current: SpokenSentence | null) {
  const cursorRef = useRef({ key: "", end: 0 });

  useEffect(() => {
    const registry = highlightRegistry();
    if (!registry) return;
    if (!current) {
      registry.delete(HIGHLIGHT_NAME);
      return;
    }
    const from =
      cursorRef.current.key === current.key && current.index > 0
        ? cursorRef.current.end
        : 0;
    const root = document.querySelector(`[data-speech-key="${current.key}"]`);
    const found = root ? findSentenceRange(root, current.text, from) : null;
    if (!found) {
      registry.delete(HIGHLIGHT_NAME);
      return;
    }
    cursorRef.current = { key: current.key, end: found.end };
    registry.set(HIGHLIGHT_NAME, new Highlight(found.range));
  }, [current]);

  useEffect(() => () => void highlightRegistry()?.delete(HIGHLIGHT_NAME), []);
}
