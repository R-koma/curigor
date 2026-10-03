"use client";

import { useState, useRef, useCallback, useMemo } from "react";
import { fetchAPI } from "@/lib/api";
import type { PreparedImage } from "@/lib/image";
import type { IntakeAnswers, IntakeCard } from "@/lib/intake";
import type { ProgressAspect } from "@/lib/progress";
import { createSpeechBus, type SpeechBus } from "@/lib/speech-bus";

type MessageRole = "user" | "assistant";

const TYPEWRITER_INTERVAL_MS = 25;
const TYPEWRITER_BATCH_SIZE = 1;
const NOTE_POLL_INTERVAL_MS = 2000;
const NOTE_POLL_TIMEOUT_MS = 5 * 60 * 1000;

export const SEND_FAILED_MESSAGE =
  "接続が切れているため送信できませんでした。再接続後に送信してください";

export interface ChatImage {
  url: string; // 送信直後は data URL、履歴復元時は配信エンドポイントの object URL
}

export interface ChatMessage {
  role: MessageRole;
  content: string;
  images?: ChatImage[];
  intakeCard?: IntakeCard;
  speechKey?: string;
}

interface ServerMessage {
  type:
    | "assistant_message"
    | "assistant_message_chunk"
    | "assistant_message_end"
    | "intake_question"
    | "note_generated"
    | "feedback_generated"
    | "session_started"
    | "session_resumed"
    | "session_ended"
    | "cancel_last_message_success"
    | "cancel_last_message_error"
    | "pending_message_rolled_back"
    | "error";
  content?: string;
  detail?: string;
  note_id?: string;
  topic?: string;
  summary?: string;
  understanding_level?: string;
  strength?: string;
  improvements?: string;
  cancelled_content?: string;
  session_id?: string;
  session_type?: "learning" | "review";
  progress?: LearningProgress | null;
  card?: IntakeCard;
}

export interface LearningProgress {
  reached_aspects: string[];
  target_count: number;
  is_complete: boolean;
  aspects?: ProgressAspect[];
}

interface Feedback {
  understanding_level: string;
  strength: string;
  improvements: string;
}

interface NoteStatusResponse {
  status: string;
  session_type: string;
  note_id?: string | null;
  topic?: string | null;
  summary?: string | null;
  feedback?: Feedback | null;
}

export interface StartLearningOptions {
  learning_goal?: string;
  raw_transcript?: string;
  auto_sent?: boolean;
}

interface UseChatWebSocketReturn {
  messages: ChatMessage[];
  isConnected: boolean;
  isLoading: boolean;
  isSessionEnded: boolean;
  isGeneratingNote: boolean;
  generatedNote: { note_id: string; topic: string; summary: string } | null;
  feedback: Feedback | null;
  error: string | null;
  editingMessage: string | null;
  editingRawTranscript: string | null;
  editingAutoSent: boolean;
  speechBus: SpeechBus;
  sessionId: string | null;
  progress: LearningProgress | null;
  sessionTopic: string | null;
  startLearning: (topic: string, options?: StartLearningOptions) => void;
  startReview: (noteId: string) => void;
  resumeSession: (sessionId: string, initialMessages: ChatMessage[]) => void;
  sendMessage: (
    content: string,
    images?: PreparedImage[],
    intakeAnswers?: IntakeAnswers,
    rawTranscript?: string,
    autoSent?: boolean,
  ) => boolean;
  endSession: () => void;
  cancelLastMessage: () => void;
  clearEditingMessage: () => void;
  resetSession: () => void;
}

function withResumedSpeechKeys(
  sessionId: string,
  messages: ChatMessage[],
): ChatMessage[] {
  return messages.map((message, index) =>
    message.role === "assistant" && !message.speechKey
      ? { ...message, speechKey: `resumed-${sessionId}-${index}` }
      : message,
  );
}

export function useChatWebSocket(): UseChatWebSocketReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSessionEnded, setIsSessionEnded] = useState(false);
  const [isGeneratingNote, setIsGeneratingNote] = useState(false);
  const [generatedNote, setGeneratedNote] = useState<{
    note_id: string;
    topic: string;
    summary: string;
  } | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingMessage, setEditingMessage] = useState<string | null>(null);
  const [editingRawTranscript, setEditingRawTranscript] = useState<
    string | null
  >(null);
  const [editingAutoSent, setEditingAutoSent] = useState(false);
  const lastSentRawRef = useRef<string | null>(null);
  const lastSentAutoRef = useRef(false);
  const speechBus = useMemo(() => createSpeechBus(), []);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [progress, setProgress] = useState<LearningProgress | null>(null);
  const [sessionTopic, setSessionTopic] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pendingTextRef = useRef<string>("");
  const liveSpeechKeyRef = useRef<string | null>(null);
  const typewriterTimerRef = useRef<ReturnType<typeof setInterval> | null>(
    null,
  );
  const pollAbortRef = useRef<AbortController | null>(null);

  const startTypewriter = useCallback(() => {
    if (typewriterTimerRef.current !== null) return;

    typewriterTimerRef.current = setInterval(() => {
      if (pendingTextRef.current.length === 0) return;

      const batch = pendingTextRef.current.slice(0, TYPEWRITER_BATCH_SIZE);
      pendingTextRef.current = pendingTextRef.current.slice(
        TYPEWRITER_BATCH_SIZE,
      );

      const speechKey = liveSpeechKeyRef.current ?? undefined;
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant") {
          return [
            ...prev.slice(0, -1),
            { ...last, content: last.content + batch },
          ];
        }
        return [
          ...prev,
          { role: "assistant" as MessageRole, content: batch, speechKey },
        ];
      });
    }, TYPEWRITER_INTERVAL_MS);
  }, []);

  const flushTypewriter = useCallback(() => {
    if (typewriterTimerRef.current !== null) {
      clearInterval(typewriterTimerRef.current);
      typewriterTimerRef.current = null;
    }
    const remaining = pendingTextRef.current;
    pendingTextRef.current = "";
    if (remaining.length === 0) return;

    const speechKey = liveSpeechKeyRef.current ?? undefined;
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant") {
        return [
          ...prev.slice(0, -1),
          { ...last, content: last.content + remaining },
        ];
      }
      return [
        ...prev,
        { role: "assistant" as MessageRole, content: remaining, speechKey },
      ];
    });
  }, []);

  const discardTypewriter = useCallback(() => {
    if (typewriterTimerRef.current !== null) {
      clearInterval(typewriterTimerRef.current);
      typewriterTimerRef.current = null;
    }
    pendingTextRef.current = "";
  }, []);

  const pollNoteStatus = useCallback(async (sessionId: string) => {
    pollAbortRef.current?.abort();
    const controller = new AbortController();
    pollAbortRef.current = controller;

    const startedAt = Date.now();
    while (!controller.signal.aborted) {
      if (Date.now() - startedAt > NOTE_POLL_TIMEOUT_MS) {
        setError("ノート生成がタイムアウトしました");
        setIsGeneratingNote(false);
        return;
      }

      try {
        const data = await fetchAPI<NoteStatusResponse>(
          `/api/dialogue-sessions/${sessionId}/note-status`,
        );

        if (data.status === "completed") {
          if (data.session_type === "learning" && data.note_id && data.topic) {
            setGeneratedNote({
              note_id: data.note_id,
              topic: data.topic,
              summary: data.summary ?? "",
            });
          } else if (data.session_type === "review" && data.feedback) {
            setFeedback(data.feedback);
          }
          setIsGeneratingNote(false);
          return;
        }

        if (data.status === "failed") {
          setError("ノート生成に失敗しました");
          setIsGeneratingNote(false);
          return;
        }
      } catch (e) {
        if (controller.signal.aborted) return;
        setError(
          e instanceof Error ? e.message : "ステータス取得に失敗しました",
        );
        setIsGeneratingNote(false);
        return;
      }

      await new Promise<void>((resolve) => {
        const t = setTimeout(resolve, NOTE_POLL_INTERVAL_MS);
        controller.signal.addEventListener("abort", () => {
          clearTimeout(t);
          resolve();
        });
      });
    }
  }, []);

  const connect = useCallback(async () => {
    const res = await fetch("/api/auth/token");
    const { token } = await res.json();
    if (!token) {
      setError("認証トークンの取得に失敗しました");
      return;
    }

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const ws = new WebSocket(`${wsUrl}/ws/chat`);

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "authenticate", token }));
      setIsConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      const data: ServerMessage = JSON.parse(event.data);

      switch (data.type) {
        case "assistant_message": {
          const speechKey = crypto.randomUUID();
          speechBus.text(speechKey, data.content ?? "");
          speechBus.end();
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: data.content ?? "", speechKey },
          ]);
          setIsLoading(false);
          break;
        }

        case "assistant_message_chunk": {
          liveSpeechKeyRef.current ??= crypto.randomUUID();
          speechBus.text(liveSpeechKeyRef.current, data.content ?? "");
          pendingTextRef.current += data.content ?? "";
          startTypewriter();
          break;
        }

        case "assistant_message_end":
          flushTypewriter();
          speechBus.end();
          liveSpeechKeyRef.current = null;
          setIsLoading(false);
          if (data.progress) setProgress(data.progress);
          break;

        case "intake_question": {
          flushTypewriter();
          liveSpeechKeyRef.current = null;
          const speechKey = crypto.randomUUID();
          speechBus.text(speechKey, data.content ?? "");
          speechBus.end();
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: data.content ?? "",
              intakeCard: data.card,
              speechKey,
            },
          ]);
          if (data.topic) setSessionTopic(data.topic);
          break;
        }

        case "note_generated":
          setGeneratedNote({
            note_id: data.note_id ?? "",
            topic: data.topic ?? "",
            summary: data.summary ?? "",
          });
          setIsGeneratingNote(false);
          break;

        case "session_started":
        case "session_resumed":
          if (data.session_id) setSessionId(data.session_id);
          if (data.progress) setProgress(data.progress);
          break;

        case "feedback_generated":
          setFeedback({
            understanding_level: data.understanding_level ?? "",
            strength: data.strength ?? "",
            improvements: data.improvements ?? "",
          });
          break;

        case "session_ended":
          flushTypewriter();
          setIsSessionEnded(true);
          setIsLoading(false);
          if (data.session_id) {
            pollNoteStatus(data.session_id);
          } else {
            setIsGeneratingNote(false);
          }
          break;

        case "cancel_last_message_success":
          flushTypewriter();
          pendingTextRef.current = "";
          setMessages((prev) => prev.slice(0, -2));
          setEditingMessage(data.cancelled_content ?? "");
          setEditingRawTranscript(lastSentRawRef.current);
          setEditingAutoSent(lastSentAutoRef.current);
          lastSentRawRef.current = null;
          lastSentAutoRef.current = false;
          break;

        case "pending_message_rolled_back":
          discardTypewriter();
          speechBus.end();
          liveSpeechKeyRef.current = null;
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            return last?.role === "assistant"
              ? prev.slice(0, -2)
              : prev.slice(0, -1);
          });
          setEditingMessage(data.content ?? "");
          break;

        case "cancel_last_message_error":
          setError(data.detail ?? "Cancel failed");
          break;

        case "error":
          speechBus.end();
          liveSpeechKeyRef.current = null;
          setError(data.detail ?? "Unknown error");
          setIsLoading(false);
          setIsGeneratingNote(false);
          break;
      }
    };

    ws.onclose = () => {
      speechBus.abort();
      liveSpeechKeyRef.current = null;
      setIsConnected(false);
    };

    ws.onerror = () => {
      setError("WebSocket connection failed");
      setIsConnected(false);
    };

    wsRef.current = ws;
  }, [
    pollNoteStatus,
    startTypewriter,
    flushTypewriter,
    discardTypewriter,
    speechBus,
  ]);

  const startLearning = useCallback(
    (topic: string, options?: StartLearningOptions) => {
      connect();

      const payload: {
        type: "start_learning";
        topic: string;
        learning_goal?: string;
        raw_transcript?: string;
        auto_sent?: boolean;
      } = { type: "start_learning", topic };

      const goal = options?.learning_goal?.trim();
      if (goal) payload.learning_goal = goal;
      if (options?.raw_transcript)
        payload.raw_transcript = options.raw_transcript;
      if (options?.auto_sent) payload.auto_sent = true;

      const checkAndSend = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify(payload));
          lastSentRawRef.current = options?.raw_transcript ?? null;
          lastSentAutoRef.current = options?.auto_sent === true;
          setMessages([{ role: "user", content: topic }]);
          setIsLoading(true);
          setIsSessionEnded(false);
          setGeneratedNote(null);
          setFeedback(null);
          setProgress(null);
          setSessionTopic(null);
        } else {
          setTimeout(checkAndSend, 50);
        }
      };
      checkAndSend();
    },
    [connect],
  );

  const startReview = useCallback(
    (noteId: string) => {
      connect();

      const checkAndSend = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(
            JSON.stringify({ type: "start_review", note_id: noteId }),
          );
          setMessages([]);
          setIsLoading(true);
          setIsSessionEnded(false);
          setGeneratedNote(null);
          setFeedback(null);
          setProgress(null);
        } else {
          setTimeout(checkAndSend, 50);
        }
      };
      checkAndSend();
    },
    [connect],
  );

  const resumeSession = useCallback(
    (sid: string, initialMessages: ChatMessage[]) => {
      connect();
      speechBus.abort();
      liveSpeechKeyRef.current = null;
      setSessionId(sid);
      setMessages(withResumedSpeechKeys(sid, initialMessages));
      setIsSessionEnded(false);
      setGeneratedNote(null);
      setFeedback(null);
      setProgress(null);

      const checkAndSend = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(
            JSON.stringify({ type: "resume_session", session_id: sid }),
          );
        } else {
          setTimeout(checkAndSend, 50);
        }
      };
      checkAndSend();
    },
    [connect, speechBus],
  );

  const sendMessage = useCallback(
    (
      content: string,
      images?: PreparedImage[],
      intakeAnswers?: IntakeAnswers,
      rawTranscript?: string,
      autoSent?: boolean,
    ) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN)
        return false;

      const payload: {
        type: "user_message";
        content: string;
        client_message_id: string;
        images?: PreparedImage[];
        intake_answers?: IntakeAnswers;
        raw_transcript?: string;
        auto_sent?: boolean;
      } = {
        type: "user_message",
        content,
        client_message_id: crypto.randomUUID(),
      };
      if (images && images.length > 0) payload.images = images;
      if (intakeAnswers) payload.intake_answers = intakeAnswers;
      if (rawTranscript) payload.raw_transcript = rawTranscript;
      if (autoSent) payload.auto_sent = true;

      wsRef.current.send(JSON.stringify(payload));
      lastSentRawRef.current = rawTranscript ?? null;
      lastSentAutoRef.current = autoSent === true;
      setMessages((prev) => [
        ...prev,
        {
          role: "user",
          content,
          images: images?.map((img) => ({
            url: `data:${img.mime_type};base64,${img.data}`,
          })),
        },
      ]);
      setIsLoading(true);
      return true;
    },
    [],
  );

  const endSession = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    wsRef.current.send(JSON.stringify({ type: "end_session" }));
    setIsLoading(true);
    setIsGeneratingNote(true);
  }, []);

  const cancelLastMessage = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    wsRef.current.send(JSON.stringify({ type: "cancel_last_message" }));
  }, []);

  const clearEditingMessage = useCallback(() => {
    setEditingMessage(null);
    setEditingRawTranscript(null);
    setEditingAutoSent(false);
  }, []);

  const resetSession = useCallback(() => {
    pollAbortRef.current?.abort();
    pollAbortRef.current = null;
    if (typewriterTimerRef.current !== null) {
      clearInterval(typewriterTimerRef.current);
      typewriterTimerRef.current = null;
    }
    pendingTextRef.current = "";
    speechBus.abort();
    liveSpeechKeyRef.current = null;
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      if (
        wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING
      ) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
    setMessages([]);
    setIsConnected(false);
    setIsLoading(false);
    setIsSessionEnded(false);
    setIsGeneratingNote(false);
    setGeneratedNote(null);
    setFeedback(null);
    setError(null);
    setEditingMessage(null);
    setSessionId(null);
    setProgress(null);
    setSessionTopic(null);
  }, [speechBus]);

  return {
    messages,
    isConnected,
    isLoading,
    isSessionEnded,
    isGeneratingNote,
    generatedNote,
    feedback,
    error,
    editingMessage,
    editingRawTranscript,
    editingAutoSent,
    speechBus,
    sessionId,
    progress,
    sessionTopic,
    startLearning,
    startReview,
    resumeSession,
    sendMessage,
    endSession,
    cancelLastMessage,
    clearEditingMessage,
    resetSession,
  };
}
