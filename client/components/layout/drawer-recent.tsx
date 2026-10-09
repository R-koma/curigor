"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRightIcon, HistoryIcon } from "lucide-react";
import { fetchAPI } from "@/lib/api";
import { activeSessionHref, type ActiveSession } from "@/lib/active-session";
import { Skeleton } from "@/components/ui/skeleton";

const RECENT_NOTES_LIMIT = 5;

interface RecentNote {
  id: string;
  topic: string;
}

type Loaded<T> =
  | { status: "loading" }
  | { status: "failed" }
  | { status: "ok"; value: T };

const SECTION_LABEL = "px-3 pb-1 text-2xs font-medium text-muted-foreground";
const ROW =
  "flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm transition-colors hover:bg-muted";

export function DrawerRecent() {
  const [session, setSession] = useState<Loaded<ActiveSession | null>>({
    status: "loading",
  });
  const [notes, setNotes] = useState<Loaded<RecentNote[]>>({
    status: "loading",
  });

  useEffect(() => {
    let active = true;
    fetchAPI<ActiveSession | null>("/api/dialogue-sessions/active")
      .then((value) => active && setSession({ status: "ok", value }))
      .catch(() => active && setSession({ status: "failed" }));
    fetchAPI<{ notes: RecentNote[] }>("/api/notes")
      .then(
        (res) =>
          active &&
          setNotes({
            status: "ok",
            value: res.notes.slice(0, RECENT_NOTES_LIMIT),
          }),
      )
      .catch(() => active && setNotes({ status: "failed" }));
    return () => {
      active = false;
    };
  }, []);

  const resumable = session.status === "ok" ? session.value : null;
  const resumeHref = resumable ? activeSessionHref(resumable) : null;

  return (
    <div className="space-y-4">
      {resumable && resumeHref && (
        <section>
          <p className={SECTION_LABEL}>続きから</p>
          <Link href={resumeHref} className={ROW}>
            <HistoryIcon
              className="size-4 shrink-0 text-brand-text"
              aria-hidden
            />
            <span className="truncate">
              {resumable.topic ?? "（タイトル未設定）"}
            </span>
          </Link>
        </section>
      )}

      {notes.status === "loading" && (
        <div className="space-y-2 px-3">
          <Skeleton className="h-4 w-20 rounded" />
          <Skeleton className="h-8 w-full rounded-lg" />
          <Skeleton className="h-8 w-full rounded-lg" />
        </div>
      )}

      {notes.status === "ok" && (
        <section>
          <p className={SECTION_LABEL}>最近のノート</p>
          {notes.value.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">
              まだノートはありません
            </p>
          ) : (
            <ul>
              {notes.value.map((note) => (
                <li key={note.id}>
                  <Link href={`/notes/${note.id}`} className={ROW}>
                    <span className="truncate">{note.topic}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <Link
            href="/notes"
            className="flex min-h-11 items-center gap-1 px-3 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            すべて見る
            <ArrowRightIcon className="size-3.5" aria-hidden />
          </Link>
        </section>
      )}
    </div>
  );
}
