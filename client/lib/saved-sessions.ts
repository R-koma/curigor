import { fetchAPI } from "@/lib/api";

export interface SavedSession {
  session_id: string;
  session_type: "learning" | "review" | "explore";
  topic: string | null;
  note_id: string | null;
  last_activity_at: string;
  expires_at: string;
  last_assistant_excerpt: string | null;
  progress: { reached: number; target: number } | null;
}

export const EXPIRY_WARNING_DAYS = 7;

const DAY_MS = 86_400_000;

export function fetchSavedSessions(): Promise<SavedSession[]> {
  return fetchAPI<SavedSession[]>("/api/dialogue-sessions/saved");
}

// note_id を持たない古い復習セッションは再開先を特定できない
export function savedSessionHref(session: SavedSession): string | null {
  if (session.session_type === "review") {
    return session.note_id
      ? `/review/${session.note_id}?session=${session.session_id}`
      : null;
  }
  return `/learn?session=${session.session_id}`;
}

export function findSavedReview(
  sessions: SavedSession[],
  noteId: string,
): SavedSession | null {
  return (
    sessions.find((s) => s.session_type === "review" && s.note_id === noteId) ??
    null
  );
}

export function daysUntilExpiry(expiresAt: string, now: Date): number {
  const days = Math.ceil(
    (new Date(expiresAt).getTime() - now.getTime()) / DAY_MS,
  );
  return Math.max(0, days);
}
