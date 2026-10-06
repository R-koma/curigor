"use client";

import { LoadingOverlay } from "@/components/ui/loading-overlay";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useChatWebSocket, type VoiceMeta } from "@/hooks/use-chat-websocket";
import { useErrorToast } from "@/hooks/use-error-toast";
import {
  useVoiceConversation,
  type VoiceUtterance,
} from "@/hooks/use-voice-conversation";
import { fetchAPI } from "@/lib/api";
import { loadResumableMessages, isResumableStatus } from "@/lib/session";
import type { PreparedImage } from "@/lib/image";
import { useNavbarSlot } from "@/context/navbar-slot-context";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ChatInput } from "@/components/chat/chat-input";
import { VoicePanel } from "@/components/chat/voice-panel";
import { MessageSpeechButton } from "@/components/chat/message-speech-button";
import { MessageCopyButton } from "@/components/chat/message-copy-button";
import { TypingIndicator } from "@/components/chat/typing-indicator";
import {
  LearningProgressIndicator,
  ProgressAdvanceNotice,
} from "@/components/chat/learning-progress";
import { IntakeAnsweredNotice } from "@/components/chat/intake-answered-notice";
import { useProgressAdvanceNotice } from "@/hooks/use-progress-advance-notice";
import { useProgressPanel } from "@/hooks/use-progress-panel";
import { AppLogo } from "@/components/brand/app-logo";
import { NavbarTopic } from "@/components/chat/navbar-topic";
import { EndSessionButton } from "@/components/chat/end-session-button";
import { ReconnectingIndicator } from "@/components/chat/reconnecting-indicator";
import { IntakeCardView } from "@/components/chat/intake-card";
import { VoiceIntakePrompt } from "@/components/chat/voice-intake-prompt";
import { intakeSpeechText } from "@/lib/intake";
import { TopicCorrectionConfirm } from "@/components/chat/topic-correction-confirm";
import { topicCorrectionAnswerText } from "@/lib/topic-correction";
import { Markdown } from "@/components/ui/markdown";
import { closeOpenCodeFence } from "@/lib/chat-markdown";
import { ArrowRightIcon, HistoryIcon, XIcon } from "lucide-react";
import { EditResendButton } from "@/components/chat/edit-resend-button";

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
    setRestoredTranscript(null);
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
    setRestoredTranscript(
      editingRawTranscript
        ? { text: editingRawTranscript, autoSent: editingAutoSent }
        : null,
    );
    clearEditingMessage();
  }

  const lastMessage = messages[messages.length - 1];
  const choicePending =
    (lastMessage?.intakeCard !== undefined ||
      lastMessage?.topicCorrectionCard !== undefined) &&
    !isSessionEnded;

  const progressPanel = useProgressPanel(progress);

  const displayTopic = sessionTopic ?? topic;
  const isChatVisible = isConnected || messages.length > 0;

  useEffect(() => {
    if (isChatVisible && displayTopic) {
      setNavbarCenter(
        <div className="flex items-center gap-3">
          <NavbarTopic topic={displayTopic} />
          <div className="h-4 w-px bg-border" />
          {progress && (
            <LearningProgressIndicator
              progress={progress}
              highlighted={progressNotice !== null}
              open={progressPanel.open}
              onOpenChange={progressPanel.setOpen}
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
    progressPanel.open,
    progressPanel.setOpen,
    endSession,
    router,
    setNavbarCenter,
  ]);

  const handleStartLearning = (
    content: string,
    rawTranscript?: string,
    autoSent?: boolean,
    voice?: VoiceMeta,
  ) => {
    const utterance = content.trim();
    if (!utterance) return;
    setTopic(utterance);
    setInput("");
    setRestoredTranscript(null);
    startLearning(
      utterance,
      rawTranscript
        ? {
            raw_transcript: rawTranscript,
            ...(autoSent ? { auto_sent: true } : {}),
            ...(autoSent && voice
              ? {
                  stt_method: voice.sttMethod,
                  stt_latency_ms: voice.sttLatencyMs,
                }
              : {}),
          }
        : undefined,
    );
  };

  const handleSendMessage = (
    content: string,
    images?: PreparedImage[],
    rawTranscript?: string,
    autoSent?: boolean,
    voice?: VoiceMeta,
  ): boolean => {
    if (!content.trim() && (!images || images.length === 0)) return false;
    const sent = sendMessage(
      content,
      images,
      undefined,
      rawTranscript,
      autoSent,
      voice,
    );
    if (sent) {
      setInput("");
      setRestoredTranscript(null);
    }
    return sent;
  };

  const voiceMeta = (u: VoiceUtterance): VoiceMeta => ({
    sttMethod: u.sttMethod,
    sttLatencyMs: u.sttLatencyMs,
  });

  const conversation = useVoiceConversation({
    sessionId,
    bus: speechBus,
    isResponding: isLoading,
    holdForReview: choicePending,
    topic: sessionTopic ?? (topic || null),
    onSend: (u) => {
      if (!isChatVisible) {
        handleStartLearning(u.content, u.rawTranscript, true, voiceMeta(u));
        return true;
      }
      return handleSendMessage(
        u.content,
        undefined,
        u.rawTranscript,
        true,
        voiceMeta(u),
      );
    },
    onHold: (u) => {
      setInput(u.content);
      setRestoredTranscript({ text: u.rawTranscript, autoSent: false });
    },
  });
  const answeringByVoice =
    conversation.status !== "off" || restoredTranscript !== null;
  useErrorToast(conversation.error);
  useErrorToast(conversation.speechError);
  const stopConversation = conversation.stop;

  useEffect(() => {
    if (isSessionEnded) stopConversation();
  }, [isSessionEnded, stopConversation]);

  const previousSessionParamRef = useRef(sessionParam);
  useEffect(() => {
    if (previousSessionParamRef.current && !sessionParam) stopConversation();
    previousSessionParamRef.current = sessionParam;
  }, [sessionParam, stopConversation]);

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
                <Tooltip>
                  <TooltipTrigger asChild>
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
                      aria-label="前回の会話を削除"
                    >
                      <XIcon className="size-3.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>前回の会話を削除</TooltipContent>
                </Tooltip>
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
          <div className="space-y-8 pt-4">
            <h1 className="flex items-center justify-center gap-2 text-2xl font-bold tracking-tight text-foreground">
              <AppLogo className="h-8" />
              何を学びますか？
            </h1>
            <div>
              {conversation.status !== "off" ? (
                <VoicePanel
                  status={conversation.status}
                  segments={conversation.segments}
                  speed={conversation.speed}
                  holdForReview={false}
                  onSpeedChange={conversation.setSpeed}
                  onPause={conversation.pause}
                  onResume={conversation.resume}
                  onSendNow={() => void conversation.sendNow()}
                  onDiscard={conversation.discard}
                  onEnd={conversation.stop}
                />
              ) : (
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
                  onVoiceStart={conversation.stopSpeech}
                  onStartConversation={() => {
                    setRestoredTranscript(null);
                    void conversation.start();
                  }}
                />
              )}
            </div>
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
                <IntakeAnsweredNotice
                  key={i}
                  onOpenPanel={progressPanel.openPanel}
                />
              );
            }
            const activeIntakeCard =
              msg.intakeCard && i === messages.length - 1 && !isSessionEnded
                ? msg.intakeCard
                : null;
            const activeTopicCorrection =
              msg.topicCorrectionCard &&
              i === messages.length - 1 &&
              !isSessionEnded
                ? msg.topicCorrectionCard
                : null;
            const isLastUserMessage =
              msg.role === "user" &&
              i > 0 &&
              !msg.topicCorrectionAnswered &&
              !messages[i - 1]?.intakeCard &&
              !messages[i - 1]?.topicCorrectionCard &&
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
                  {activeTopicCorrection && (
                    <TopicCorrectionConfirm
                      disabled={isLoading}
                      onAnswer={(answer) =>
                        sendMessage(
                          topicCorrectionAnswerText(answer),
                          undefined,
                          undefined,
                          undefined,
                          undefined,
                          undefined,
                          answer,
                        )
                      }
                    />
                  )}
                  {activeIntakeCard &&
                    (answeringByVoice ? (
                      <VoiceIntakePrompt
                        card={activeIntakeCard}
                        disabled={isLoading}
                        onSkip={(content, answers) =>
                          sendMessage(content, undefined, answers)
                        }
                      />
                    ) : (
                      <IntakeCardView
                        card={activeIntakeCard}
                        disabled={isLoading}
                        onSubmit={(content, answers) =>
                          sendMessage(content, undefined, answers)
                        }
                      />
                    ))}
                </div>
                <div className="flex flex-col items-center gap-1">
                  {msg.content && <MessageCopyButton content={msg.content} />}
                  {canSpeak && speechKey && (
                    <MessageSpeechButton
                      speaking={conversation.activeKey === speechKey}
                      onPlay={() =>
                        conversation.playMessage(
                          speechKey,
                          msg.intakeCard
                            ? intakeSpeechText(msg.content, msg.intakeCard)
                            : msg.content,
                        )
                      }
                      onStop={conversation.stopSpeech}
                    />
                  )}
                  {isLastUserMessage && (
                    <EditResendButton
                      onClick={() => {
                        conversation.stop();
                        cancelLastMessage();
                      }}
                    />
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
            {conversation.status !== "off" ? (
              <VoicePanel
                status={conversation.status}
                segments={conversation.segments}
                speed={conversation.speed}
                holdForReview={choicePending}
                onSpeedChange={conversation.setSpeed}
                onPause={conversation.pause}
                onResume={conversation.resume}
                onSendNow={() => void conversation.sendNow()}
                onDiscard={conversation.discard}
                onEnd={conversation.stop}
              />
            ) : (
              <ChatInput
                value={input}
                onChange={setInput}
                onSend={handleSendMessage}
                isLoading={isLoading}
                sessionId={sessionId}
                allowVoice
                onVoiceStart={conversation.stopSpeech}
                onStartConversation={() => {
                  setRestoredTranscript(null);
                  void conversation.start();
                }}
                restoredTranscript={restoredTranscript}
              />
            )}
          </div>
        </div>
      )}

      {isGeneratingNote && <LoadingOverlay message="ノート作成中..." />}
    </div>
  );
}
