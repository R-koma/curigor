import { fetchAPI, fetchImageObjectURL } from "@/lib/api";
import type { ChatMessage } from "@/hooks/use-chat-websocket";
import type { IntakeAnswers, IntakeCard } from "@/lib/intake";

interface SessionImageItem {
  id: string;
  mime_type: string;
  image_order: number;
}

interface SessionMessageItem {
  role: "user" | "assistant";
  content: string;
  message_order: number;
  images: SessionImageItem[];
  intake_card?: IntakeCard | null;
  intake_answers?: IntakeAnswers | null;
}

interface SessionMessagesResponse {
  session_id: string;
  session_type: "learning" | "review";
  status: string;
  note_id: string | null;
  topic?: string | null;
  messages: SessionMessageItem[];
}

export interface ResumableSession {
  sessionType: "learning" | "review";
  status: string;
  noteId: string | null;
  topic: string | null;
  messages: ChatMessage[];
}

const RESUMABLE_STATUSES = new Set(["in_progress", "disconnect"]);

export function isResumableStatus(status: string): boolean {
  return RESUMABLE_STATUSES.has(status);
}

// review は先頭メッセージ（ノートのトピック）の除外を呼び出し側が行う。
export async function loadResumableMessages(
  sessionId: string,
): Promise<ResumableSession> {
  const data = await fetchAPI<SessionMessagesResponse>(
    `/api/dialogue-sessions/${sessionId}/messages`,
  );

  const messages: ChatMessage[] = await Promise.all(
    data.messages.map(
      async ({ role, content, images, intake_card, intake_answers }) => ({
        role,
        content,
        intakeCard: intake_card ?? undefined,
        ...(intake_answers ? { intakeAnswered: true as const } : {}),
        images:
          images.length > 0
            ? await Promise.all(
                images.map(async (img) => ({
                  url: await fetchImageObjectURL(
                    `/api/dialogue-sessions/${sessionId}/images/${img.id}`,
                  ),
                })),
              )
            : undefined,
      }),
    ),
  );

  return {
    sessionType: data.session_type,
    status: data.status,
    noteId: data.note_id,
    topic: data.topic ?? null,
    messages,
  };
}
