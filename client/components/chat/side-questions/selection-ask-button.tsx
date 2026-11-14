"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MessageSquareIcon } from "lucide-react";
import { anchorFromRange } from "@/lib/text-anchor";

export interface SelectedPassage {
  root: HTMLElement;
  quote: string;
  occurrence: number;
}

const SELECTABLE = "[data-side-selectable]";

function selectedPassage(): { passage: SelectedPassage; rect: DOMRect } | null {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
    return null;
  }
  const range = selection.getRangeAt(0);
  const container = range.commonAncestorContainer;
  const element =
    container.nodeType === Node.ELEMENT_NODE
      ? (container as Element)
      : container.parentElement;
  const root = element?.closest<HTMLElement>(SELECTABLE);
  if (!root) return null;
  const anchor = anchorFromRange(root, range);
  if (!anchor) return null;
  return { passage: { root, ...anchor }, rect: range.getBoundingClientRect() };
}

export function SelectionAskButton({
  onAsk,
}: {
  onAsk: (passage: SelectedPassage) => void;
}) {
  const [shown, setShown] = useState<{
    passage: SelectedPassage;
    left: number;
    top: number;
  } | null>(null);
  const timerRef = useRef<number | null>(null);

  const evaluate = useCallback(() => {
    const found = selectedPassage();
    setShown(
      found
        ? {
            passage: found.passage,
            left: found.rect.left + found.rect.width / 2,
            top: found.rect.top - 8,
          }
        : null,
    );
  }, []);

  useEffect(() => {
    const later = () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(evaluate, 0);
    };
    const onSelectionChange = () => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed) setShown(null);
    };
    const hide = () => setShown(null);
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") hide();
    };
    document.addEventListener("mouseup", later);
    document.addEventListener("keyup", later);
    document.addEventListener("selectionchange", onSelectionChange);
    document.addEventListener("keydown", onKeyDown);
    window.addEventListener("scroll", hide, true);
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      document.removeEventListener("mouseup", later);
      document.removeEventListener("keyup", later);
      document.removeEventListener("selectionchange", onSelectionChange);
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("scroll", hide, true);
    };
  }, [evaluate]);

  if (!shown) return null;

  return (
    <button
      type="button"
      style={{ left: shown.left, top: shown.top }}
      onMouseDown={(e) => e.preventDefault()}
      onMouseUp={(e) => e.stopPropagation()}
      onClick={() => {
        const { passage } = shown;
        setShown(null);
        window.getSelection()?.removeAllRanges();
        onAsk(passage);
      }}
      className="fixed z-menu hidden -translate-x-1/2 -translate-y-full items-center gap-1.5 rounded-full bg-foreground py-1.5 pr-3.5 pl-3 text-sm font-medium text-background shadow-lg md:inline-flex pointer-coarse:hidden"
    >
      <MessageSquareIcon aria-hidden className="size-3.5" />
      ここについて質問
    </button>
  );
}
