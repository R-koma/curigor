import { fetchAPI } from "@/lib/api";

export interface ActiveSession {
  session_id: string;
  session_type: "learning" | "review" | "explore";
  status: string;
  started_at: string;
  topic: string | null;
  note_id: string | null;
}

// note_id を持たない古い復習セッションは再開先を特定できない
export function activeSessionHref(session: ActiveSession): string | null {
  if (session.session_type === "review") {
    return session.note_id
      ? `/review/${session.note_id}?session=${session.session_id}`
      : null;
  }
  return `/learn?session=${session.session_id}`;
}

export async function fetchActiveSession(): Promise<ActiveSession | null> {
  return (
    (await fetchAPI<ActiveSession | null>("/api/dialogue-sessions/active")) ??
    null
  );
}
