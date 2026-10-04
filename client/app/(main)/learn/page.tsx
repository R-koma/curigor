"use client";

import { LoadingOverlay } from "@/components/ui/loading-overlay";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useChatWebSocket } from "@/hooks/use-chat-websocket";
import { useErrorToast } from "@/hooks/use-error-toast";
import { useVoiceMode } from "@/hooks/use-voice-mode";
import { fetchAPI } from "@/lib/api";
import { loadResumableMessages, isResumableStatus } from "@/lib/session";
import type { PreparedImage } from "@/lib/image";
import { useNavbarSlot } from "@/context/navbar-slot-context";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { ChatInput } from "@/components/chat/chat-input";
import { VoiceModeToggle } from "@/components/chat/voice-mode-toggle";
import { MessageSpeechButton } from "@/components/chat/message-speech-button";
import { MessageCopyButton } from "@/components/chat/message-copy-button";
import { TypingIndicator } from "@/components/chat/typing-indicator";
import {
  canOpenProgressPanel,
  LearningProgressIndicator,
  ProgressAdvanceNotice,
} from "@/components/chat/learning-progress";
import { IntakeAnsweredNotice } from "@/components/chat/intake-answered-notice";
import { useProgressAdvanceNotice } from "@/hooks/use-progress-advance-notice";
import { EndSessionButton } from "@/components/chat/end-session-button";
import { ReconnectingIndicator } from "@/components/chat/reconnecting-indicator";
import { TopicSuggestions } from "@/components/chat/topic-suggestions";
import { IntakeCardView } from "@/components/chat/intake-card";
import { Markdown } from "@/components/ui/markdown";
import { closeOpenCodeFence } from "@/lib/chat-markdown";
import { ArrowRightIcon, HistoryIcon, PencilIcon, XIcon } from "lucide-react";

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
    isReconnecting,
    isLoading,
    isSessionEnded,
    isGeneratingNote,
    generatedNote,
    error,
    editingMessage,
    editingRawTranscript,
    editingAutoSent,
    speechBus,
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
  useErrorToast(error);
  const progressNotice = useProgressAdvanceNotice(progress);
  const voiceMode = useVoiceMode({ sessionId, bus: speechBus });
  const stopVoice = voiceMode.stop;
  const [restoredTranscript, setRestoredTranscript] = useState<{
    text: string;
    autoSent: boolean;
  } | null>(null);

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

  useEffect(() => {
    if (isSessionEnded) stopVoice();
  }, [isSessionEnded, stopVoice]);

  if (editingMessage !== null) {
    setInput(editingMessage);
    setRestoredTranscript(
      editingRawTranscript
        ? { text: editingRawTranscript, autoSent: editingAutoSent }
        : null,
    );
    clearEditingMessage();
  }

  const intakePending =
    messages[messages.length - 1]?.intakeCard !== undefined && !isSessionEnded;

  const [progressPanelOpen, setProgressPanelOpen] = useState(false);
  const openProgressPanel =
    progress && canOpenProgressPanel(progress)
      ? () => setProgressPanelOpen(true)
      : undefined;

  const displayTopic = sessionTopic ?? topic;
  const isChatVisible = isConnected || messages.length > 0;

  useEffect(() => {
    if (isChatVisible && displayTopic) {
      setNavbarCenter(
        <div className="flex items-center gap-3">
          <h1 className="max-w-xs truncate text-sm font-semibold">
            {displayTopic}
          </h1>
          <div className="h-4 w-px bg-border" />
          {progress && (
            <LearningProgressIndicator
              progress={progress}
              highlighted={progressNotice !== null}
              open={progressPanelOpen}
              onOpenChange={setProgressPanelOpen}
            />
          )}
          {progress && <ProgressAdvanceNotice notice={progressNotice} />}
          {isReconnecting && <ReconnectingIndicator />}
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
    isChatVisible,
    isReconnecting,
    displayTopic,
    progress,
    progressNotice,
    progressPanelOpen,
    endSession,
    router,
    setNavbarCenter,
  ]);

  const handleStartLearning = (
    content: string,
    rawTranscript?: string,
    autoSent?: boolean,
  ) => {
    const utterance = content.trim();
    if (!utterance) return;
    voiceMode.interrupt();
    setTopic(utterance);
    setInput("");
    startLearning(
      utterance,
      rawTranscript
        ? {
            raw_transcript: rawTranscript,
            ...(autoSent ? { auto_sent: true } : {}),
          }
        : undefined,
    );
  };

  const handleSendMessage = (
    content: string,
    images?: PreparedImage[],
    rawTranscript?: string,
    autoSent?: boolean,
  ): boolean => {
    if (!content.trim() && (!images || images.length === 0)) return false;
    voiceMode.interrupt();
    const sent = sendMessage(
      content,
      images,
      undefined,
      rawTranscript,
      autoSent,
    );
    if (sent) setInput("");
    return sent;
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
            <div className="group relative overflow-hidden rounded-2xl border border-brand/20 bg-linear-to-br from-brand/8 via-background to-background p-5 shadow-sm transition-all hover:border-brand/40">
              <div className="pointer-events-none absolute -top-12 -right-12 size-32 rounded-full bg-brand/10 blur-3xl" />

              <div className="relative flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <div className="flex size-6 items-center justify-center rounded-full bg-brand/15 text-brand-text">
                    <HistoryIcon className="size-3.5" />
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
                  className="-mt-1 -mr-1 size-7 shrink-0 cursor-pointer rounded-full text-muted-foreground opacity-60 transition-opacity hover:bg-background hover:text-foreground hover:opacity-100"
                  title="前回の会話を削除"
                >
                  <XIcon className="size-3.5" />
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
                <span className="flex shrink-0 items-center gap-1.5 rounded-full bg-brand px-3.5 py-1.5 text-xs font-medium text-brand-foreground shadow-sm transition-colors group-hover/btn:bg-brand/90">
                  続きから再開
                  <ArrowRightIcon className="size-3.5" />
                </span>
              </button>
            </div>
          )}
          <div className="space-y-5 pt-4">
            <h1 className="text-center text-2xl font-bold tracking-tight text-foreground">
              何を学びますか？
            </h1>
            <div>
              <VoiceModeToggle
                enabled={voiceMode.enabled}
                onChange={voiceMode.setEnabled}
                error={voiceMode.error}
                speaking={voiceMode.isSpeaking}
                onStop={voiceMode.stop}
              />
              <ChatInput
                value={input}
                onChange={setInput}
                onSend={(content, _images, rawTranscript, autoSent) =>
                  handleStartLearning(content, rawTranscript, autoSent)
                }
                isLoading={false}
                placeholder="学びたいこと、目的や状況を書いてください"
                allowImages={false}
                allowVoice
                voiceMode={voiceMode.enabled}
                autoSendVoice={voiceMode.enabled}
                onVoiceStart={
                  voiceMode.enabled ? voiceMode.interrupt : undefined
                }
              />
            </div>
            <TopicSuggestions onSelect={handleStartLearning} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-6">
        <div className="mx-auto max-w-3xl space-y-4 py-6">
          {messages.map((msg, i) => {
            if (msg.role === "user" && msg.intakeAnswered) {
              return (
                <IntakeAnsweredNotice key={i} onOpenPanel={openProgressPanel} />
              );
            }
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
            const speechKey =
              msg.role === "assistant" ? msg.speechKey : undefined;
            const canSpeak =
              speechKey !== undefined &&
              msg.content !== "" &&
              !(isLoading && i === messages.length - 1);

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
                  {canSpeak && speechKey && (
                    <MessageSpeechButton
                      speaking={voiceMode.activeKey === speechKey}
                      onPlay={() =>
                        voiceMode.playMessage(speechKey, msg.content)
                      }
                      onStop={voiceMode.stop}
                    />
                  )}
                  {isLastUserMessage && (
                    <button
                      type="button"
                      onClick={() => {
                        voiceMode.stop();
                        cancelLastMessage();
                      }}
                      className="mt-2 cursor-pointer opacity-0 transition-opacity group-hover:opacity-100"
                      title="編集して再送信"
                    >
                      <PencilIcon className="size-4 text-muted-foreground hover:text-foreground" />
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
            <VoiceModeToggle
              enabled={voiceMode.enabled}
              onChange={voiceMode.setEnabled}
              error={voiceMode.error}
              speaking={voiceMode.isSpeaking}
              onStop={voiceMode.stop}
            />
            <ChatInput
              value={input}
              onChange={setInput}
              onSend={handleSendMessage}
              isLoading={isLoading}
              sessionId={sessionId}
              allowVoice
              voiceMode={voiceMode.enabled}
              autoSendVoice={voiceMode.enabled && !intakePending}
              onVoiceStart={voiceMode.enabled ? voiceMode.interrupt : undefined}
              restoredTranscript={restoredTranscript}
            />
          </div>
        </div>
      )}

      {isGeneratingNote && <LoadingOverlay message="ノート作成中..." />}
    </div>
  );
}
