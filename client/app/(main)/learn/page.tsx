"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useChatWebSocket } from "@/hooks/use-chat-websocket";
import { fetchAPI } from "@/lib/api";
import { loadResumableMessages, isResumableStatus } from "@/lib/session";
import type { PreparedImage } from "@/lib/image";
import { useNavbarSlot } from "@/context/navbar-slot-context";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageCopyButton } from "@/components/chat/message-copy-button";
import { TypingIndicator } from "@/components/chat/typing-indicator";
import { LearningProgressIndicator } from "@/components/chat/learning-progress";
import { EndSessionButton } from "@/components/chat/end-session-button";
import { TopicSuggestions } from "@/components/chat/topic-suggestions";
import { IntakeCardView } from "@/components/chat/intake-card";
import { Markdown } from "@/components/ui/markdown";
import { closeOpenCodeFence } from "@/lib/chat-markdown";
import {
  ArrowRightIcon,
  HistoryIcon,
  Loader2Icon,
  PencilIcon,
  XIcon,
} from "lucide-react";

interface ActiveSessionResponse {
  session_id: string;
  session_type: "learning" | "review";
  status: string;
  started_at: string;
  topic: string | null;
  note_id: string | null;
}

export default function LearnPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionParam = searchParams.get("session");
  const [topic, setTopic] = useState("");
  const [input, setInput] = useState("");
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [resumableSession, setResumableSession] =
    useState<ActiveSessionResponse | null>(null);
  const restoredSessionRef = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { setNavbarCenter } = useNavbarSlot();

  const {
    messages,
    isConnected,
    isLoading,
    isSessionEnded,
    isGeneratingNote,
    generatedNote,
    error,
    editingMessage,
    sessionId,
    progress,
    sessionTopic,
    startLearning,
    resumeSession,
    sendMessage,
    endSession,
    cancelLastMessage,
    clearEditingMessage,
    resetSession,
  } = useChatWebSocket();

  useEffect(() => {
    if (sessionParam) {
      if (restoredSessionRef.current === sessionParam) return;
      restoredSessionRef.current = sessionParam;
      setIsBootstrapping(true);
      setResumableSession(null);

      (async () => {
        try {
          const {
            sessionType,
            status,
            noteId,
            messages,
            topic: sessionTopicFromApi,
          } = await loadResumableMessages(sessionParam);
          if (!isResumableStatus(status)) return;
          // 復習は復習ページ（復習バッジ・ノート更新ボタン）で再開する。learn は learning 専用。
          if (sessionType === "review") {
            if (noteId) {
              router.replace(`/review/${noteId}?session=${sessionParam}`);
            }
            return;
          }
          setTopic(sessionTopicFromApi ?? messages[0]?.content ?? "");
          resumeSession(sessionParam, messages);
        } catch {
          // セッションが無効化 / 404 の場合は新規開始フローに戻す
        } finally {
          setIsBootstrapping(false);
        }
      })();
      return;
    }

    restoredSessionRef.current = null;
    resetSession();
    /* eslint-disable react-hooks/set-state-in-effect */
    setTopic("");
    setInput("");
    setIsBootstrapping(true);
    /* eslint-enable react-hooks/set-state-in-effect */
    fetchAPI<ActiveSessionResponse | null>("/api/dialogue-sessions/active")
      .then((res) => {
        if (res?.session_id) {
          setResumableSession(res);
        } else {
          setResumableSession(null);
        }
      })
      .catch(() => {
        // 取得失敗時は再開バナーを出さずに新規学習フォームを表示する
      })
      .finally(() => setIsBootstrapping(false));
  }, [sessionParam, resumeSession, resetSession, router]);

  useEffect(() => {
    if (!sessionId) return;
    if (sessionParam === sessionId) return;
    restoredSessionRef.current = sessionId;
    router.replace(`/learn?session=${sessionId}`);
  }, [sessionId, sessionParam, router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    if (!generatedNote) return;
    router.push(`/notes/${generatedNote.note_id}`);
  }, [generatedNote, router]);

  if (editingMessage !== null) {
    setInput(editingMessage);
    clearEditingMessage();
  }

  const displayTopic = sessionTopic ?? topic;

  useEffect(() => {
    if (isConnected && displayTopic) {
      setNavbarCenter(
        <div className="flex items-center gap-3">
          <h1 className="max-w-xs truncate text-sm font-semibold">
            {displayTopic}
          </h1>
          <div className="h-4 w-px bg-border" />
          {progress && <LearningProgressIndicator progress={progress} />}
          <EndSessionButton
            highlighted={progress?.is_complete ?? false}
            onClick={endSession}
          />
        </div>,
      );
    } else {
      setNavbarCenter(null);
    }
    return () => setNavbarCenter(null);
  }, [
    isConnected,
    displayTopic,
    progress,
    endSession,
    router,
    setNavbarCenter,
  ]);

  const handleStartLearning = (content: string) => {
    const utterance = content.trim();
    if (!utterance) return;
    setTopic(utterance);
    setInput("");
    startLearning(utterance);
  };

  const handleSendMessage = (
    content: string,
    images?: PreparedImage[],
    rawTranscript?: string,
  ) => {
    if (!content.trim() && (!images || images.length === 0)) return;
    sendMessage(content, images, undefined, rawTranscript);
    setInput("");
  };

  if (isBootstrapping) {
    // 再開時はチャット履歴が、新規時は学習フォームが描画されるため骨格を出し分ける
    if (sessionParam) {
      return (
        <div className="flex h-full flex-col">
          <div className="flex-1 overflow-y-auto px-6">
            <div className="mx-auto max-w-3xl space-y-4 py-6">
              <div className="flex justify-start">
                <Skeleton className="h-16 w-full max-w-md rounded-2xl" />
              </div>
              <div className="flex justify-end">
                <Skeleton className="h-16 w-full max-w-sm rounded-2xl" />
              </div>
              <div className="flex justify-start">
                <Skeleton className="h-16 w-full max-w-md rounded-2xl" />
              </div>
            </div>
          </div>
          <div className="border-t p-4">
            <Skeleton className="h-12 w-full rounded-xl" />
          </div>
        </div>
      );
    }

    return (
      <div className="flex h-full items-center justify-center overflow-y-auto p-4">
        <div className="my-4 w-full max-w-2xl space-y-6">
          <Skeleton className="mx-auto h-8 w-48" />
          <Skeleton className="h-24 w-full rounded-2xl" />
        </div>
      </div>
    );
  }

  // 復習は復習ページで再開する。note_id を持たない古い復習セッションは再開先を特定できないため出さない。
  const resumableHref = resumableSession
    ? resumableSession.session_type === "review"
      ? resumableSession.note_id
        ? `/review/${resumableSession.note_id}?session=${resumableSession.session_id}`
        : null
      : `/learn?session=${resumableSession.session_id}`
    : null;

  if (messages.length === 0 && !isConnected) {
    return (
      <div className="flex h-full items-center justify-center overflow-y-auto p-4">
        <div className="w-full max-w-2xl my-4 space-y-4">
          {resumableSession && resumableHref && (
            <div className="group relative overflow-hidden rounded-2xl border border-blue-500/20 bg-linear-to-br from-blue-500/8 via-background to-background p-5 shadow-sm transition-all hover:border-blue-500/40 hover:shadow-md">
              <div className="pointer-events-none absolute -top-12 -right-12 h-32 w-32 rounded-full bg-blue-500/10 blur-3xl" />

              <div className="relative flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-500/15 text-blue-500">
                    <HistoryIcon className="h-3.5 w-3.5" />
                  </div>
                  <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                    前回の会話
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={async () => {
                    const target = resumableSession;
                    setResumableSession(null);
                    try {
                      await fetchAPI(
                        `/api/dialogue-sessions/${target.session_id}`,
                        { method: "DELETE" },
                      );
                    } catch {
                      setResumableSession(target);
                    }
                  }}
                  className="-mt-1 -mr-1 h-7 w-7 shrink-0 cursor-pointer rounded-full text-muted-foreground opacity-60 transition-opacity hover:bg-background hover:text-foreground hover:opacity-100"
                  title="前回の会話を削除"
                >
                  <XIcon className="h-3.5 w-3.5" />
                </Button>
              </div>

              <button
                type="button"
                onClick={() => router.push(resumableHref)}
                className="group/btn relative mt-3 flex w-full items-center justify-between gap-4 text-left cursor-pointer"
              >
                <p className="line-clamp-2 text-lg font-semibold leading-snug text-foreground">
                  {resumableSession.topic ?? "（タイトル未設定）"}
                </p>
                <span className="flex shrink-0 items-center gap-1.5 rounded-full bg-blue-600 px-3.5 py-1.5 text-xs font-medium text-white shadow-sm transition-transform group-hover/btn:translate-x-0.5">
                  続きから再開
                  <ArrowRightIcon className="h-3.5 w-3.5" />
                </span>
              </button>
            </div>
          )}
          <div className="space-y-5 pt-4">
            <h1 className="text-center text-2xl font-bold tracking-tight text-foreground">
              何を学びますか？
            </h1>
            <ChatInput
              value={input}
              onChange={setInput}
              onSend={(content) => handleStartLearning(content)}
              isLoading={false}
              placeholder="学びたいこと、目的や状況を書いてください"
              allowImages={false}
            />
            <TopicSuggestions onSelect={handleStartLearning} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {error && (
        <div className="px-6 py-2 text-sm text-destructive">{error}</div>
      )}

      <div className="flex-1 overflow-y-auto px-6">
        <div className="mx-auto max-w-3xl space-y-4 py-6">
          {messages.map((msg, i) => {
            const activeIntakeCard =
              msg.intakeCard && i === messages.length - 1 && !isSessionEnded
                ? msg.intakeCard
                : null;
            const isLastUserMessage =
              msg.role === "user" &&
              i > 0 &&
              !messages[i - 1]?.intakeCard &&
              i === messages.length - 2 &&
              messages[messages.length - 1].role === "assistant" &&
              !isLoading &&
              !isSessionEnded;

            return (
              <div
                key={i}
                className={`group flex items-start gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
              >
                <div
                  className={`max-w-full rounded-2xl px-4 py-3 text-base leading-relaxed ${
                    msg.role === "user" ? "bg-muted" : ""
                  }`}
                >
                  {msg.images && msg.images.length > 0 && (
                    <div className="mb-2 flex flex-wrap gap-2">
                      {msg.images.map((image, imageIndex) => (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          key={imageIndex}
                          src={image.url}
                          alt="添付画像"
                          className="max-h-64 rounded-lg border object-contain"
                        />
                      ))}
                    </div>
                  )}
                  {msg.content && (
                    <Markdown
                      variant="chat"
                      className="[&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
                    >
                      {closeOpenCodeFence(msg.content)}
                    </Markdown>
                  )}
                  {activeIntakeCard && (
                    <IntakeCardView
                      card={activeIntakeCard}
                      disabled={isLoading}
                      onSubmit={(content, answers) =>
                        sendMessage(content, undefined, answers)
                      }
                    />
                  )}
                </div>
                <div className="flex flex-col items-center gap-1">
                  {msg.content && <MessageCopyButton content={msg.content} />}
                  {isLastUserMessage && (
                    <button
                      type="button"
                      onClick={cancelLastMessage}
                      className="mt-2 cursor-pointer opacity-0 transition-opacity group-hover:opacity-100"
                      title="編集して再送信"
                    >
                      <PencilIcon className="h-4 w-4 text-muted-foreground hover:text-foreground" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}

          {isLoading && messages[messages.length - 1]?.role !== "assistant" && (
            <TypingIndicator />
          )}

          {isSessionEnded && !generatedNote && !isGeneratingNote && (
            <div className="mx-auto max-w-md rounded-lg border p-4 text-center">
              <p className="text-sm text-muted-foreground">
                セッションが終了しました
              </p>
              <Button asChild variant="link" className="mt-2">
                <Link href="/dashboard">ダッシュボードに戻る</Link>
              </Button>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {!isSessionEnded && (
        <div className="shrink-0 bg-background/95 backdrop-blur-sm px-6 py-4">
          <div className="mx-auto max-w-3xl">
            <ChatInput
              value={input}
              onChange={setInput}
              onSend={handleSendMessage}
              isLoading={isLoading}
              sessionId={sessionId}
            />
          </div>
        </div>
      )}

      {isGeneratingNote && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs">
          <div className="flex flex-col items-center gap-4 rounded-xl border bg-background px-8 py-6 shadow-lg">
            <Loader2Icon className="h-8 w-8 animate-spin text-primary" />
            <p className="text-base font-medium">ノート作成中...</p>
          </div>
        </div>
      )}
    </div>
  );
}
