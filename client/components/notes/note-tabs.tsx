"use client";

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { Badge } from "@/components/ui/badge";
import { understandingBadge } from "@/lib/badge";
import {
  NOTE_TAB_LABELS,
  NOTE_TABS,
  tabForHash,
  type NoteTab,
} from "@/lib/note-tabs";
import { cn } from "@/lib/utils";

interface NoteTabsContextValue {
  active: NoteTab;
  select: (tab: NoteTab) => void;
}

const NoteTabsContext = createContext<NoteTabsContextValue | null>(null);

function useNoteTabs(): NoteTabsContextValue {
  const value = useContext(NoteTabsContext);
  if (!value) throw new Error("NoteTabsProvider is missing");
  return value;
}

export function NoteTabsProvider({
  initialTab,
  children,
}: {
  initialTab: NoteTab;
  children: ReactNode;
}) {
  const [active, setActive] = useState<NoteTab>(initialTab);

  useEffect(() => {
    const followHash = () => {
      const tab = tabForHash(window.location.hash);
      if (!tab) return;
      setActive(tab);
      const id = decodeURIComponent(window.location.hash.slice(1));
      requestAnimationFrame(() =>
        document.getElementById(id)?.scrollIntoView({ block: "start" }),
      );
    };
    const frame = requestAnimationFrame(followHash);
    window.addEventListener("hashchange", followHash);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("hashchange", followHash);
    };
  }, []);

  return (
    <NoteTabsContext.Provider value={{ active, select: setActive }}>
      {children}
    </NoteTabsContext.Provider>
  );
}

function TabMarker({
  tab,
  understandingLevel,
  suggestedLinkCount,
}: {
  tab: NoteTab;
  understandingLevel: string | null;
  suggestedLinkCount: number;
}) {
  if (tab === "understanding" && understandingLevel) {
    const badge = understandingBadge(understandingLevel);
    return (
      <Badge variant={badge.variant} className="px-1.5 font-normal">
        {badge.label}
      </Badge>
    );
  }
  if (tab === "connections" && suggestedLinkCount > 0) {
    return (
      <Badge variant="secondary" className="px-1.5 font-normal">
        {suggestedLinkCount}
        <span className="sr-only">件の候補</span>
      </Badge>
    );
  }
  return null;
}

export function NoteTabBar({
  controls,
  understandingLevel,
  suggestedLinkCount,
}: {
  controls: Record<NoteTab, string[]>;
  understandingLevel: string | null;
  suggestedLinkCount: number;
}) {
  const { active, select } = useNoteTabs();
  const sentinelRef = useRef<HTMLDivElement>(null);
  const barRef = useRef<HTMLDivElement>(null);

  const choose = (tab: NoteTab) => {
    select(tab);
    const sentinel = sentinelRef.current;
    const bar = barRef.current;
    if (
      sentinel &&
      bar &&
      sentinel.getBoundingClientRect().top < bar.getBoundingClientRect().top
    ) {
      sentinel.scrollIntoView({ block: "start" });
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const step =
      event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (step === 0) return;
    event.preventDefault();
    const index = NOTE_TABS.indexOf(active);
    const next =
      NOTE_TABS[(index + step + NOTE_TABS.length) % NOTE_TABS.length];
    choose(next);
    document.getElementById(`note-tab-${next}`)?.focus();
  };

  return (
    <>
      <div ref={sentinelRef} aria-hidden className="md:hidden" />
      <div
        ref={barRef}
        role="tablist"
        aria-label="ノートの表示"
        className="sticky top-0 z-raised -mx-4 mb-6 flex border-b bg-background px-4 md:hidden"
      >
        {NOTE_TABS.map((tab) => {
          const selected = tab === active;
          return (
            <button
              key={tab}
              id={`note-tab-${tab}`}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={controls[tab].join(" ") || undefined}
              tabIndex={selected ? 0 : -1}
              onClick={() => choose(tab)}
              onKeyDown={onKeyDown}
              className={cn(
                "-mb-px flex h-11 flex-1 items-center justify-center gap-1.5 border-b-2 text-sm transition-colors",
                selected
                  ? "border-brand font-medium text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {NOTE_TAB_LABELS[tab]}
              <TabMarker
                tab={tab}
                understandingLevel={understandingLevel}
                suggestedLinkCount={suggestedLinkCount}
              />
            </button>
          );
        })}
      </div>
    </>
  );
}

export function NoteTabSection({
  tab,
  as: Tag = "div",
  id,
  className,
  children,
}: {
  tab: NoteTab;
  as?: "div" | "aside";
  id?: string;
  className?: string;
  children: ReactNode;
}) {
  const { active } = useNoteTabs();
  return (
    <Tag id={id} className={cn(active !== tab && "max-md:hidden", className)}>
      {children}
    </Tag>
  );
}
