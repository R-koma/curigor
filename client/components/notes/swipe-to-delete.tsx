"use client";

import {
  useEffect,
  useRef,
  useState,
  type MouseEvent,
  type ReactNode,
  type TouchEvent,
} from "react";
import { Trash2Icon } from "lucide-react";
import { useCoarsePointer } from "@/hooks/use-coarse-pointer";
import { cn } from "@/lib/utils";

const ACTION_WIDTH = 88;
const DIRECTION_THRESHOLD = 8;

interface SwipeToDeleteProps {
  label: string;
  onDelete: () => void;
  disabled?: boolean;
  children: ReactNode;
}

interface Drag {
  startX: number;
  startY: number;
  base: number;
  horizontal: boolean | null;
}

export function SwipeToDelete({
  label,
  onDelete,
  disabled = false,
  children,
}: SwipeToDeleteProps) {
  const coarse = useCoarsePointer();
  const [offset, setOffset] = useState(0);
  const [dragging, setDragging] = useState(false);
  const dragRef = useRef<Drag | null>(null);
  const swipedRef = useRef(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const open = offset !== 0 && !dragging;

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: Event) => {
      if (!rootRef.current?.contains(event.target as Node)) setOffset(0);
    };
    document.addEventListener("touchstart", closeOutside);
    return () => document.removeEventListener("touchstart", closeOutside);
  }, [open]);

  if (!coarse || disabled) return <>{children}</>;

  const handleTouchStart = (event: TouchEvent) => {
    const touch = event.touches[0];
    dragRef.current = {
      startX: touch.clientX,
      startY: touch.clientY,
      base: offset,
      horizontal: null,
    };
    swipedRef.current = false;
  };

  const handleTouchMove = (event: TouchEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    const touch = event.touches[0];
    const dx = touch.clientX - drag.startX;
    const dy = touch.clientY - drag.startY;
    if (drag.horizontal === null) {
      if (Math.max(Math.abs(dx), Math.abs(dy)) < DIRECTION_THRESHOLD) return;
      drag.horizontal = Math.abs(dx) > Math.abs(dy);
    }
    if (!drag.horizontal) return;
    swipedRef.current = true;
    setDragging(true);
    setOffset(Math.min(0, Math.max(-ACTION_WIDTH, drag.base + dx)));
  };

  const handleTouchEnd = () => {
    const drag = dragRef.current;
    dragRef.current = null;
    if (!drag?.horizontal) return;
    setDragging(false);
    setOffset((current) => (current < -ACTION_WIDTH / 2 ? -ACTION_WIDTH : 0));
  };

  const handleClickCapture = (event: MouseEvent) => {
    if (!swipedRef.current && offset === 0) return;
    event.preventDefault();
    event.stopPropagation();
    swipedRef.current = false;
    if (offset !== 0 && !dragRef.current) setOffset(0);
  };

  return (
    <div ref={rootRef} className="relative overflow-hidden rounded-xl">
      <button
        type="button"
        aria-label={label}
        tabIndex={open ? 0 : -1}
        onClick={() => {
          setOffset(0);
          onDelete();
        }}
        className="absolute inset-y-0 right-0 flex w-22 flex-col items-center justify-center gap-1 bg-destructive text-xs font-medium text-white"
      >
        <Trash2Icon className="size-5" aria-hidden />
        削除
      </button>
      <div
        data-testid="swipe-panel"
        style={{ transform: `translateX(${offset}px)` }}
        className={cn(
          "relative touch-pan-y rounded-xl bg-background",
          !dragging && "transition-transform duration-200",
        )}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onTouchCancel={handleTouchEnd}
        onClickCapture={handleClickCapture}
      >
        {children}
      </div>
    </div>
  );
}
