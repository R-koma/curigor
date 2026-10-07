"use client";

import { useState, useRef, useCallback, useMemo, useEffect } from "react";
import { fetchAPI } from "@/lib/api";
import type { PreparedImage } from "@/lib/image";
import {
  intakeSpeechText,
  isIntakeCard,
  type IntakeAnswers,
  type IntakeCard,
} from "@/lib/intake";
import type { ProgressAspect } from "@/lib/progress";
import { createSpeechBus, type SpeechBus } from "@/lib/speech-bus";
import type { SttMethod } from "@/lib/stt/types";
import {
  isTopicCorrectionCard,
  type TopicCorrectionAnswer,
  type TopicCorrectionCard,
} from "@/lib/topic-correction";

type MessageRole = "user" | "assistant";

const TYPEWRITER_INTERVAL_MS = 25;
const TYPEWRITER_BATCH_SIZE = 1;
const NOTE_POLL_INTERVAL_MS = 2000;
const NOTE_POLL_TIMEOUT_MS = 5 * 60 * 1000;
const RECONNECT_DELAYS_MS = [1000, 2000, 5000, 10_000, 30_000];

export const SEND_FAILED_MESSAGE =
  "接続が切れているため送信できませんでした。再接続後に送信してください";
export const CONNECTION_LOST_MESSAGE =
  "接続が切れました。ページを開き直してください";
export const RECONNECT_FAILED_MESSAGE =
  "サーバーに再接続できませんでした。通信状況を確認してください";
export const AUTH_EXPIRED_MESSAGE =
  "ログインの有効期限が切れました。再度ログインしてください";

export interface ChatImage {
  url: string; // 送信直後は data URL、履歴復元時は配信エンドポイントの object URL
}

export interface ChatMessage {
  role: MessageRole;
  content: string;
  images?: ChatImage[];
  intakeCard?: IntakeCard;
  intakeAnswered?: true;
  topicCorrectionCard?: TopicCorrectionCard;
  topicCorrectionAnswered?: true;
  speechKey?: string;
}

export interface EndConfirmation {
  creates_note: boolean;
}

interface ServerMessage {
  type:
    | "assistant_message"
    | "assistant_message_chunk"
    | "assistant_message_end"
    | "intake_question"
    | "topic_correction_question"
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
  session_type?: "learning" | "review" | "synthesis";
  progress?: LearningProgress | null;
  card?: IntakeCard | TopicCorrectionCard;
  end_confirmation?: EndConfirmation | null;
  note_skipped?: boolean;
}

export interface IntakeSummary {
  purpose: string;
  source: string;
  prior_knowledge: string;
}

export interface LearningProgress {
  reached_aspects: string[];
  target_count: number;
  is_complete: boolean;
  aspects?: ProgressAspect[];
  intake?: IntakeSummary | null;
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

export interface VoiceMeta {
  sttMethod: SttMethod;
  sttLatencyMs: number;
}

export interface StartLearningOptions {
  learning_goal?: string;
  raw_transcript?: string;
  auto_sent?: boolean;
  stt_method?: SttMethod;
  stt_latency_ms?: number;
}

interface UseChatWebSocketReturn {
  messages: ChatMessage[];
  isConnected: boolean;
  isReconnecting: boolean;
  isLoading: boolean;
  isSessionEnded: boolean;
  isGeneratingNote: boolean;
  isSynthesisSaved: boolean;
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
  endConfirmation: EndConfirmation | null;
  noteSkipped: boolean;
  dismissEndConfirmation: () => void;
  startLearning: (topic: string, options?: StartLearningOptions) => void;
  startReview: (noteId: string, focusAspectIds?: string[] | null) => void;
  startSynthesis: (collectionId: string) => void;
  resumeSession: (sessionId: string, initialMessages: ChatMessage[]) => void;
  sendMessage: (
    content: string,
    images?: PreparedImage[],
    intakeAnswers?: IntakeAnswers,
    rawTranscript?: string,
    autoSent?: boolean,
    voice?: VoiceMeta,
    topicCorrectionAnswer?: TopicCorrectionAnswer,
  ) => boolean;
  endSession: () => boolean;
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
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSessionEnded, setIsSessionEnded] = useState(false);
  const [isGeneratingNote, setIsGeneratingNote] = useState(false);
  const [endConfirmation, setEndConfirmation] =
    useState<EndConfirmation | null>(null);
  const [noteSkipped, setNoteSkipped] = useState(false);
  const [isSynthesisSaved, setIsSynthesisSaved] = useState(false);
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
  const sessionIdRef = useRef<string | null>(null);
  const resumableRef = useRef(false);
  const sessionEndedRef = useRef(false);
  const awaitingResumeRef = useRef(false);
  const pendingSendRef = useRef<{
    content: string;
    fromIntakeCard: boolean;
  } | null>(null);
  const interruptedSendRef = useRef(false);
  const reconciledRef = useRef(false);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectInFlightRef = useRef(false);
  const mountedRef = useRef(true);
  const connectRef = useRef<(resumeSessionId?: string) => Promise<void>>(
    async () => {},
  );

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
        setError("ノートの作成がタイムアウトしました。もう一度お試しください");
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
          } else if (data.session_type === "synthesis") {
            setIsSynthesisSaved(true);
          }
          setIsGeneratingNote(false);
          return;
        }

        if (data.status === "failed") {
          setError("ノートを作成できませんでした。もう一度お試しください");
          setIsGeneratingNote(false);
          return;
        }
      } catch (e) {
        if (controller.signal.aborted) return;
        setError(
          e instanceof Error
            ? e.message
            : "ノートの作成状況を確認できませんでした。通信状況を確認してください",
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

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const reconnectNow = useCallback(() => {
    const sid = sessionIdRef.current;
    if (sid === null || reconnectInFlightRef.current) return;
    reconnectInFlightRef.current = true;
    void connectRef.current(sid).finally(() => {
      reconnectInFlightRef.current = false;
    });
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current || !resumableRef.current) return;
    if (reconnectTimerRef.current !== null) return;
    const attempt = reconnectAttemptRef.current;
    if (attempt >= RECONNECT_DELAYS_MS.length) {
      setIsReconnecting(false);
      setError(RECONNECT_FAILED_MESSAGE);
      return;
    }
    reconnectAttemptRef.current = attempt + 1;
    setIsReconnecting(true);
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      reconnectNow();
    }, RECONNECT_DELAYS_MS[attempt]);
  }, [reconnectNow]);

  const stopReconnecting = useCallback(() => {
    resumableRef.current = false;
    awaitingResumeRef.current = false;
    clearReconnectTimer();
    setIsReconnecting(false);
  }, [clearReconnectTimer]);

  const connect = useCallback(
    async (resumeSessionId?: string) => {
      if (!resumeSessionId) sessionEndedRef.current = false;

      let token: string | undefined;
      try {
        const res = await fetch("/api/auth/token");
        ({ token } = await res.json());
      } catch {
        if (resumeSessionId) {
          scheduleReconnect();
        } else {
          setError(
            "ログインの確認に失敗しました。ページを再読み込みしてください",
          );
        }
        return;
      }
      if (!token) {
        if (resumeSessionId) {
          stopReconnecting();
          setError(AUTH_EXPIRED_MESSAGE);
        } else {
          setError(
            "ログインの確認に失敗しました。ページを再読み込みしてください",
          );
        }
        return;
      }
      if (
        resumeSessionId &&
        (!resumableRef.current || sessionIdRef.current !== resumeSessionId)
      ) {
        return;
      }

      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
      const ws = new WebSocket(`${wsUrl}/ws/chat`);

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "authenticate", token }));
        if (resumeSessionId) {
          awaitingResumeRef.current = true;
          ws.send(
            JSON.stringify({
              type: "resume_session",
              session_id: resumeSessionId,
            }),
          );
        }
        setIsConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        const data: ServerMessage = JSON.parse(event.data);

        switch (data.type) {
          case "assistant_message": {
            pendingSendRef.current = null;
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
            pendingSendRef.current = null;
            flushTypewriter();
            speechBus.end();
            liveSpeechKeyRef.current = null;
            setIsLoading(false);
            if (data.progress) setProgress(data.progress);
            if (data.topic) setSessionTopic(data.topic);
            setEndConfirmation(data.end_confirmation ?? null);
            break;

          case "intake_question": {
            pendingSendRef.current = null;
            flushTypewriter();
            liveSpeechKeyRef.current = null;
            const speechKey = crypto.randomUUID();
            speechBus.text(
              speechKey,
              isIntakeCard(data.card)
                ? intakeSpeechText(data.content ?? "", data.card)
                : (data.content ?? ""),
            );
            speechBus.end();
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content: data.content ?? "",
                intakeCard: isIntakeCard(data.card) ? data.card : undefined,
                speechKey,
              },
            ]);
            if (data.topic) setSessionTopic(data.topic);
            break;
          }

          case "topic_correction_question": {
            pendingSendRef.current = null;
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
                topicCorrectionCard: isTopicCorrectionCard(data.card)
                  ? data.card
                  : undefined,
                speechKey,
              },
            ]);
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
            if (data.session_id) {
              setSessionId(data.session_id);
              sessionIdRef.current = data.session_id;
            }
            resumableRef.current = data.session_type !== "synthesis";
            sessionEndedRef.current = false;
            if (data.type === "session_resumed") {
              reconciledRef.current = false;
              const unanswered = pendingSendRef.current;
              if (interruptedSendRef.current && unanswered) {
                discardTypewriter();
                speechBus.end();
                liveSpeechKeyRef.current = null;
                setMessages((prev) => {
                  const lastUser = prev.findLastIndex((m) => m.role === "user");
                  return lastUser === -1 ? prev : prev.slice(0, lastUser);
                });
                setEditingMessage(
                  unanswered.fromIntakeCard ? "" : unanswered.content,
                );
                pendingSendRef.current = null;
                reconciledRef.current = true;
              }
              interruptedSendRef.current = false;
              awaitingResumeRef.current = false;
              reconnectAttemptRef.current = 0;
              setIsReconnecting(false);
            }
            if (data.progress) setProgress(data.progress);
            if (data.type === "session_resumed")
              setEndConfirmation(data.end_confirmation ?? null);
            break;

          case "feedback_generated":
            setFeedback({
              understanding_level: data.understanding_level ?? "",
              strength: data.strength ?? "",
              improvements: data.improvements ?? "",
            });
            break;

          case "session_ended":
            sessionEndedRef.current = true;
            stopReconnecting();
            flushTypewriter();
            setIsSessionEnded(true);
            setIsLoading(false);
            setEndConfirmation(null);
            if (data.note_skipped) {
              setNoteSkipped(true);
              setIsGeneratingNote(false);
            } else if (data.session_id) {
              pollNoteStatus(data.session_id);
            } else {
              setIsGeneratingNote(false);
            }
            break;

          case "cancel_last_message_success":
            pendingSendRef.current = null;
            flushTypewriter();
            pendingTextRef.current = "";
            setMessages((prev) => prev.slice(0, -2));
            setEditingMessage(data.cancelled_content ?? "");
            setEndConfirmation(null);
            setEditingRawTranscript(lastSentRawRef.current);
            setEditingAutoSent(lastSentAutoRef.current);
            lastSentRawRef.current = null;
            lastSentAutoRef.current = false;
            break;

          case "pending_message_rolled_back":
            pendingSendRef.current = null;
            if (reconciledRef.current) {
              reconciledRef.current = false;
              break;
            }
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
            setError(data.detail ?? "発言を取り消せませんでした");
            break;

          case "error":
            pendingSendRef.current = null;
            speechBus.end();
            liveSpeechKeyRef.current = null;
            setError(
              data.detail ??
                "問題が発生しました。時間をおいてもう一度お試しください",
            );
            setIsLoading(false);
            setIsGeneratingNote(false);
            if (awaitingResumeRef.current) stopReconnecting();
            break;
        }
      };

      ws.onclose = () => {
        if (wsRef.current !== ws) return;
        speechBus.abort();
        liveSpeechKeyRef.current = null;
        setIsConnected(false);
        if (resumableRef.current) {
          interruptedSendRef.current = pendingSendRef.current !== null;
          setIsLoading(false);
          scheduleReconnect();
          return;
        }
        if (!sessionEndedRef.current) setError(CONNECTION_LOST_MESSAGE);
      };

      ws.onerror = () => {
        setIsConnected(false);
      };

      wsRef.current = ws;
    },
    [
      pollNoteStatus,
      startTypewriter,
      flushTypewriter,
      discardTypewriter,
      speechBus,
      scheduleReconnect,
      stopReconnecting,
    ],
  );

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  const startLearning = useCallback(
    (topic: string, options?: StartLearningOptions) => {
      connect();

      const payload: {
        type: "start_learning";
        topic: string;
        learning_goal?: string;
        raw_transcript?: string;
        auto_sent?: boolean;
        stt_method?: SttMethod;
        stt_latency_ms?: number;
      } = { type: "start_learning", topic };

      const goal = options?.learning_goal?.trim();
      if (goal) payload.learning_goal = goal;
      if (options?.raw_transcript)
        payload.raw_transcript = options.raw_transcript;
      if (options?.auto_sent) payload.auto_sent = true;
      if (options?.auto_sent && options.stt_method) {
        payload.stt_method = options.stt_method;
        payload.stt_latency_ms = options.stt_latency_ms;
      }

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
    (noteId: string, focusAspectIds?: string[] | null) => {
      connect();

      const checkAndSend = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(
            JSON.stringify({
              type: "start_review",
              note_id: noteId,
              ...(focusAspectIds ? { focus_aspect_ids: focusAspectIds } : {}),
            }),
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

  const startSynthesis = useCallback(
    (collectionId: string) => {
      connect();

      const checkAndSend = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(
            JSON.stringify({
              type: "start_synthesis",
              collection_id: collectionId,
            }),
          );
          setMessages([]);
          setIsLoading(true);
          setIsSessionEnded(false);
          setIsSynthesisSaved(false);
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
      voice?: VoiceMeta,
      topicCorrectionAnswer?: TopicCorrectionAnswer,
    ) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN)
        return false;
      if (awaitingResumeRef.current) return false;

      const payload: {
        type: "user_message";
        content: string;
        client_message_id: string;
        images?: PreparedImage[];
        intake_answers?: IntakeAnswers;
        topic_correction_answer?: TopicCorrectionAnswer;
        raw_transcript?: string;
        auto_sent?: boolean;
        stt_method?: SttMethod;
        stt_latency_ms?: number;
      } = {
        type: "user_message",
        content,
        client_message_id: crypto.randomUUID(),
      };
      if (images && images.length > 0) payload.images = images;
      if (intakeAnswers) payload.intake_answers = intakeAnswers;
      if (topicCorrectionAnswer)
        payload.topic_correction_answer = topicCorrectionAnswer;
      if (rawTranscript) payload.raw_transcript = rawTranscript;
      if (autoSent) payload.auto_sent = true;
      if (autoSent && voice) {
        payload.stt_method = voice.sttMethod;
        payload.stt_latency_ms = voice.sttLatencyMs;
      }

      wsRef.current.send(JSON.stringify(payload));
      pendingSendRef.current = {
        content,
        fromIntakeCard:
          intakeAnswers !== undefined || topicCorrectionAnswer !== undefined,
      };
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
          ...(intakeAnswers ? { intakeAnswered: true as const } : {}),
          ...(topicCorrectionAnswer
            ? { topicCorrectionAnswered: true as const }
            : {}),
        },
      ]);
      setEndConfirmation(null);
      setIsLoading(true);
      return true;
    },
    [],
  );

  const endSession = useCallback((): boolean => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN)
      return false;

    wsRef.current.send(JSON.stringify({ type: "end_session" }));
    setError(null);
    setEndConfirmation(null);
    setIsLoading(true);
    setIsGeneratingNote(true);
    return true;
  }, []);

  const dismissEndConfirmation = useCallback(
    () => setEndConfirmation(null),
    [],
  );

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
    stopReconnecting();
    sessionIdRef.current = null;
    sessionEndedRef.current = false;
    reconnectAttemptRef.current = 0;
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
    setEndConfirmation(null);
    setNoteSkipped(false);
  }, [speechBus, stopReconnecting]);

  useEffect(() => {
    mountedRef.current = true;

    const retryNow = () => {
      if (document.visibilityState !== "visible") return;
      if (!mountedRef.current || !resumableRef.current) return;
      const ws = wsRef.current;
      if (
        ws &&
        (ws.readyState === WebSocket.OPEN ||
          ws.readyState === WebSocket.CONNECTING)
      ) {
        return;
      }
      clearReconnectTimer();
      reconnectAttemptRef.current = 0;
      setIsReconnecting(true);
      reconnectNow();
    };

    document.addEventListener("visibilitychange", retryNow);
    window.addEventListener("online", retryNow);
    return () => {
      mountedRef.current = false;
      document.removeEventListener("visibilitychange", retryNow);
      window.removeEventListener("online", retryNow);
      clearReconnectTimer();
    };
  }, [clearReconnectTimer, reconnectNow]);

  return {
    messages,
    isConnected,
    isReconnecting,
    isLoading,
    isSessionEnded,
    isGeneratingNote,
    isSynthesisSaved,
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
    endConfirmation,
    noteSkipped,
    dismissEndConfirmation,
    startLearning,
    startReview,
    startSynthesis,
    resumeSession,
    sendMessage,
    endSession,
    cancelLastMessage,
    clearEditingMessage,
    resetSession,
  };
}
