import { headers } from "next/headers";
import { fetchAPI, getToken } from "@/lib/api";
import type { SavedSession } from "@/lib/saved-sessions";
import { SavedSessionList } from "@/components/sessions/saved-session-list";

export const dynamic = "force-dynamic";

export default async function SessionsPage() {
  const cookieHeader = (await headers()).get("cookie") ?? "";
  const token = await getToken(cookieHeader);
  const sessions = await fetchAPI<SavedSession[]>(
    "/api/dialogue-sessions/saved",
    { token },
  );

  return <SavedSessionList sessions={sessions} now={new Date()} />;
}
