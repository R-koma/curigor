"use client";

import { useEffect, useRef } from "react";
import { rangeFromAnchor } from "@/lib/text-anchor";

export interface HighlightAnchor {
  id: string;
  rootSelector: string;
  quote: string;
  occurrence: number;
}

const ALL = "side-anchor";
const HOVER = "side-anchor-hover";
const OPEN = "side-anchor-open";

function supported(): boolean {
  return (
    typeof CSS !== "undefined" &&
    "highlights" in CSS &&
    typeof Highlight !== "undefined"
  );
}

const ROOTS = "[data-message-id], [data-side-message-id]";

function rootOf(target: EventTarget | null): HTMLElement | null {
  return target instanceof Element ? target.closest<HTMLElement>(ROOTS) : null;
}

function touchesRoot(node: Node): boolean {
  const element = node instanceof Element ? node : node.parentElement;
  if (!element) return false;
  return (
    element.closest(ROOTS) !== null || element.querySelector(ROOTS) !== null
  );
}

function affectsAnchors(mutations: MutationRecord[]): boolean {
  return mutations.some(
    (m) =>
      touchesRoot(m.target) ||
      [...m.addedNodes, ...m.removedNodes].some(
        (n) =>
          n instanceof Element &&
          (n.matches(ROOTS) || n.querySelector(ROOTS) !== null),
      ),
  );
}

function hitTest(
  ranges: Map<string, Range>,
  root: HTMLElement,
  x: number,
  y: number,
): string | null {
  for (const [id, range] of ranges) {
    if (!root.contains(range.startContainer)) continue;
    for (const rect of range.getClientRects()) {
      if (
        x >= rect.left &&
        x <= rect.right &&
        y >= rect.top &&
        y <= rect.bottom
      ) {
        return id;
      }
    }
  }
  return null;
}

export function AnchorHighlights({
  anchors,
  hoverId,
  openIds,
  onOpen,
}: {
  anchors: HighlightAnchor[];
  hoverId: string | null;
  openIds: Set<string>;
  onOpen: (id: string) => void;
}) {
  const rangesRef = useRef(new Map<string, Range>());
  const scheduleRef = useRef<(() => void) | null>(null);
  const stateRef = useRef({ anchors, hoverId, openIds, onOpen });
  useEffect(() => {
    stateRef.current = { anchors, hoverId, openIds, onOpen };
  });

  useEffect(() => {
    if (!supported()) return;
    let frame: number | null = null;

    const paint = () => {
      frame = null;
      const {
        anchors: current,
        hoverId: hover,
        openIds: open,
      } = stateRef.current;
      const ranges = new Map<string, Range>();
      for (const anchor of current) {
        const root = document.querySelector<HTMLElement>(anchor.rootSelector);
        const range = root
          ? rangeFromAnchor(root, anchor.quote, anchor.occurrence)
          : null;
        if (range) ranges.set(anchor.id, range);
      }
      rangesRef.current = ranges;
      const pick = (keep: (id: string) => boolean) =>
        new Highlight(
          ...[...ranges].filter(([id]) => keep(id)).map(([, range]) => range),
        );
      CSS.highlights.set(
        ALL,
        pick(() => true),
      );
      CSS.highlights.set(
        HOVER,
        pick((id) => id === hover),
      );
      CSS.highlights.set(
        OPEN,
        pick((id) => open.has(id)),
      );
    };
    const schedule = () => {
      if (frame === null) frame = requestAnimationFrame(paint);
    };
    scheduleRef.current = schedule;

    const observer = new MutationObserver((mutations) => {
      if (affectsAnchors(mutations)) schedule();
    });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    const onClick = (e: MouseEvent) => {
      const selection = window.getSelection();
      if (selection && !selection.isCollapsed) return;
      const root = rootOf(e.target);
      if (!root) return;
      const id = hitTest(rangesRef.current, root, e.clientX, e.clientY);
      if (id) stateRef.current.onOpen(id);
    };
    const onMove = (e: MouseEvent) => {
      const root = rootOf(e.target);
      if (!root) return;
      root.style.cursor = hitTest(rangesRef.current, root, e.clientX, e.clientY)
        ? "pointer"
        : "";
    };
    document.addEventListener("click", onClick);
    document.addEventListener("mousemove", onMove);
    window.addEventListener("resize", schedule);
    schedule();
    return () => {
      if (frame !== null) cancelAnimationFrame(frame);
      observer.disconnect();
      document.removeEventListener("click", onClick);
      document.removeEventListener("mousemove", onMove);
      window.removeEventListener("resize", schedule);
      CSS.highlights.delete(ALL);
      CSS.highlights.delete(HOVER);
      CSS.highlights.delete(OPEN);
      rangesRef.current = new Map();
      scheduleRef.current = null;
    };
  }, []);

  useEffect(() => {
    scheduleRef.current?.();
  }, [hoverId, openIds, anchors]);

  return null;
}
