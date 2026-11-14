import { API_BASE_URL, fetchAPI, getToken, readApiError } from "@/lib/api";

export const MAX_SIDE_QUOTE_LENGTH = 300;
export const MAX_SIDE_DEPTH = 3;

export interface SideMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export interface SideQuestion {
  id: string;
  parentId: string | null;
  anchorMessageId: string | null;
  anchorSideMessageId: string | null;
  quote: string;
  occurrence: number;
  depth: number;
  messages: SideMessage[];
}

export type SideAnchor =
  | { anchorMessageId: string; anchorSideMessageId?: undefined }
  | { anchorSideMessageId: string; anchorMessageId?: undefined };

export type SideStreamEvent =
  | {
      type: "started";
      sideQuestionId: string;
      userMessageId: string;
      answerMessageId: string;
    }
  | { type: "chunk"; content: string }
  | { type: "end" }
  | { type: "error"; code: string; detail: string };

interface SideQuestionItem {
  id: string;
  parent_id: string | null;
  anchor_message_id: string | null;
  anchor_side_message_id: string | null;
  quote: string;
  occurrence: number;
  depth: number;
  messages: SideMessage[];
}

export async function fetchSideQuestions(
  sessionId: string,
): Promise<SideQuestion[]> {
  const data = await fetchAPI<{ side_questions: SideQuestionItem[] }>(
    `/api/dialogue-sessions/${sessionId}/side-questions`,
  );
  return data.side_questions.map((q) => ({
    id: q.id,
    parentId: q.parent_id,
    anchorMessageId: q.anchor_message_id,
    anchorSideMessageId: q.anchor_side_message_id,
    quote: q.quote,
    occurrence: q.occurrence,
    depth: q.depth,
    messages: q.messages.map(({ id, role, content }) => ({
      id,
      role,
      content,
    })),
  }));
}

export async function* parseNdjson(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<unknown> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += done
        ? decoder.decode()
        : decoder.decode(value, { stream: true });
      let newline = buffer.indexOf("\n");
      while (newline !== -1) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        if (line) yield JSON.parse(line);
        newline = buffer.indexOf("\n");
      }
      if (done) break;
    }
    const rest = buffer.trim();
    if (rest) yield JSON.parse(rest);
  } finally {
    reader.releaseLock();
  }
}

function toEvent(raw: unknown): SideStreamEvent | null {
  if (typeof raw !== "object" || raw === null) return null;
  const data = raw as Record<string, unknown>;
  const text = (key: string) =>
    typeof data[key] === "string" ? (data[key] as string) : "";
  switch (data.type) {
    case "started":
      return {
        type: "started",
        sideQuestionId: text("side_question_id"),
        userMessageId: text("user_message_id"),
        answerMessageId: text("answer_message_id"),
      };
    case "chunk":
      return { type: "chunk", content: text("content") };
    case "end":
      return { type: "end" };
    case "error":
      return { type: "error", code: text("code"), detail: text("detail") };
    default:
      return null;
  }
}

async function* postStream(
  path: string,
  body: Record<string, unknown>,
  signal?: AbortSignal,
): AsyncGenerator<SideStreamEvent> {
  const token = await getToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw await readApiError(res);
  for await (const raw of parseNdjson(res.body)) {
    const event = toEvent(raw);
    if (event) yield event;
  }
}

export function streamNewSideQuestion(
  sessionId: string,
  body: SideAnchor & { quote: string; occurrence: number; content: string },
  signal?: AbortSignal,
): AsyncGenerator<SideStreamEvent> {
  return postStream(
    `/api/dialogue-sessions/${sessionId}/side-questions`,
    {
      anchor_message_id: body.anchorMessageId ?? null,
      anchor_side_message_id: body.anchorSideMessageId ?? null,
      quote: body.quote,
      occurrence: body.occurrence,
      content: body.content,
    },
    signal,
  );
}

export function streamSideFollowUp(
  sideQuestionId: string,
  content: string,
  signal?: AbortSignal,
): AsyncGenerator<SideStreamEvent> {
  return postStream(
    `/api/side-questions/${sideQuestionId}/messages`,
    { content },
    signal,
  );
}
