"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboardIcon,
  PlusCircleIcon,
  BookOpenIcon,
  LibraryIcon,
  PanelLeftIcon,
  PanelLeftCloseIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { SidebarCalendar } from "@/components/layout/sidebar-calendar";
import { cn } from "@/lib/utils";
import { useSidebarWidth } from "@/hooks/use-sidebar-width";

const NAV_LINKS = [
  { href: "/dashboard", label: "復習", icon: LayoutDashboardIcon },
  { href: "/learn", label: "新規", icon: PlusCircleIcon },
  { href: "/notes", label: "履歴", icon: BookOpenIcon },
  { href: "/collections", label: "まとめ", icon: LibraryIcon },
];

// 開閉トランジション（duration-300）を最後まで見せてから実際に閉じるため、閉じ待機はそれより長くする
const OVERLAY_CLOSE_DELAY_MS = 350;

export function Sidebar() {
  const [expanded, setExpanded] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [isOverlayVisible, setIsOverlayVisible] = useState(false);
  // すでにオーバーレイで全幅表示中の場合、ピン留め時に一瞬56pxへ戻ってしまわないよう幅遷移を止める
  const [skipPinTransition, setSkipPinTransition] = useState(false);
  // 閉じた直後、同じ座標に現れたホバートリガーへブラウザが再ホバーを検知してしまう場合があるため、
  // 実際に aside から離れる（mouseleave）まで自動再オープンを抑止する
  const [suppressReopen, setSuppressReopen] = useState(false);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pathname = usePathname();
  const { width, isResizing, startResize } = useSidebarWidth();

  const isOverlay = !expanded && isHovering;
  const isOpen = expanded || isOverlay;

  useEffect(() => {
    if (!isOverlay) return;
    const raf = requestAnimationFrame(() => setIsOverlayVisible(true));
    return () => cancelAnimationFrame(raf);
  }, [isOverlay]);

  useEffect(() => {
    return () => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    };
  }, []);

  const clearCloseTimer = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };

  const handleAsideMouseEnter = () => {
    clearCloseTimer();
  };

  const handleTriggerMouseEnter = () => {
    clearCloseTimer();
    if (expanded || suppressReopen) return;
    setIsHovering(true);
    setIsOverlayVisible(true);
  };

  const handleTogglePin = () => {
    if (expanded) {
      // isHovering を残すと isOverlay が true に戻り、閉じたように見えなくなる
      clearCloseTimer();
      setIsHovering(false);
      setIsOverlayVisible(false);
      setSuppressReopen(true);
    } else if (isOverlay) {
      setSkipPinTransition(true);
    }
    setExpanded((prev) => !prev);
  };

  useEffect(() => {
    if (!skipPinTransition) return;
    const raf = requestAnimationFrame(() => setSkipPinTransition(false));
    return () => cancelAnimationFrame(raf);
  }, [skipPinTransition]);

  const handleMouseLeave = () => {
    setSuppressReopen(false);
    if (expanded) return;
    setIsOverlayVisible(false);
    clearCloseTimer();
    closeTimerRef.current = setTimeout(() => {
      setIsHovering(false);
    }, OVERLAY_CLOSE_DELAY_MS);
  };

  return (
    <aside
      className={cn(
        "relative flex shrink-0",
        !expanded && "w-14",
        isResizing || skipPinTransition
          ? ""
          : "transition-[width] duration-200",
      )}
      style={expanded ? { width } : undefined}
      onMouseEnter={handleAsideMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div
        className={cn(
          "flex flex-1 flex-col overflow-x-hidden overflow-y-auto border-r bg-background",
          isOverlay &&
            cn(
              "absolute inset-y-0 left-0 z-drawer shadow-lg transition-all duration-300 ease-out",
              isOverlayVisible
                ? "translate-x-0 opacity-100"
                : "-translate-x-2 opacity-0",
            ),
        )}
        style={isOverlay ? { width } : undefined}
      >
        <div className="border-b">
          {isOpen ? (
            <div className="flex items-center px-2 py-3">
              <Button
                variant="ghost"
                size="icon"
                className="size-8 shrink-0 mr-1"
                onClick={handleTogglePin}
                aria-label={
                  expanded ? "サイドバーを閉じる" : "サイドバーを開く"
                }
              >
                {expanded ? (
                  <PanelLeftCloseIcon className="size-4" />
                ) : (
                  <PanelLeftIcon className="size-4" />
                )}
              </Button>
              <Link
                href="/dashboard"
                className="flex items-center gap-2 font-bold text-lg tracking-tight min-w-0"
              >
                <span>Curigor</span>
              </Link>
            </div>
          ) : (
            <button
              className="group flex w-full items-center justify-center py-3 cursor-pointer"
              onClick={() => setExpanded(true)}
              onMouseEnter={handleTriggerMouseEnter}
              aria-label="サイドバーを開く"
            >
              <PanelLeftIcon className="size-4 text-muted-foreground transition-colors group-hover:text-foreground" />
            </button>
          )}
        </div>

        <nav className="flex flex-col gap-1 p-2">
          {NAV_LINKS.map(({ href, label, icon: Icon }) => {
            const isActive =
              pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                className={`group relative flex items-center gap-3 rounded-md px-2 py-2 text-sm transition-all duration-150 ${
                  isActive
                    ? "bg-muted font-medium text-foreground"
                    : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                } ${isOpen ? "" : "justify-center"}`}
              >
                <Icon className="size-4 shrink-0" />
                {isOpen ? (
                  <span>{label}</span>
                ) : (
                  <span className="pointer-events-none absolute left-full z-overlay ml-2 whitespace-nowrap rounded-md bg-muted px-2 py-1 text-xs text-foreground opacity-0 shadow-md transition-opacity duration-150 group-hover:opacity-100">
                    {label}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {isOpen && (
          <div className="mt-4 border-t p-2 pt-4">
            <SidebarCalendar showSkeleton={expanded} />
          </div>
        )}
      </div>

      {expanded && (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="サイドバーの幅を調整"
          onMouseDown={startResize}
          className={cn(
            "absolute top-0 right-0 h-full w-1 cursor-col-resize transition-colors hover:bg-primary/40",
            isResizing && "bg-primary/40",
          )}
        />
      )}
    </aside>
  );
}
