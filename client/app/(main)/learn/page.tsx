"use client";

import { LoadingOverlay } from "@/components/ui/loading-overlay";
import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useChatWebSocket, type VoiceMeta } from "@/hooks/use-chat-websocket";
import { useErrorToast } from "@/hooks/use-error-toast";
import {
  useVoiceConversation,
  type VoiceUtterance,
} from "@/hooks/use-voice-conversation";
import { fetchAPI } from "@/lib/api";
import { activeSessionHref, type ActiveSession } from "@/lib/active-session";
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
import { IntakeAnsweredNotice } from "@/components/chat/intake-answered-notice";
import { TopicEditedNotice } from "@/components/chat/topic-edited-notice";
import { useProgressAdvanceNotice } from "@/hooks/use-progress-advance-notice";
import { useProgressPanel } from "@/hooks/use-progress-panel";
import { SessionHeader } from "@/components/chat/session-header";
import { AppLogo } from "@/components/brand/app-logo";
import { EndSessionConfirm } from "@/components/chat/end-session-confirm";
import { SessionEndedNotice } from "@/components/chat/session-ended-notice";
import { IntakeCardView } from "@/components/chat/intake-card";
import { VoiceIntakePrompt } from "@/components/chat/voice-intake-prompt";
import { intakeSpeechText } from "@/lib/intake";
import { TopicCorrectionConfirm } from "@/components/chat/topic-correction-confirm";
import { topicCorrectionAnswerText } from "@/lib/topic-correction";
import { Markdown } from "@/components/ui/markdown";
import { closeOpenBlocks } from "@/lib/chat-markdown";
import { findTrialTopic } from "@/lib/trial";
import type { StudyMemo } from "@/lib/study-memos";
import { StartModeToggle } from "@/components/chat/start-mode-toggle";
import { SessionTypeBadge } from "@/components/chat/session-type-badge";
import { ArrowRightIcon, HistoryIcon, XIcon } from "lucide-react";
import { EditResendButton } from "@/components/chat/edit-resend-button";
import { UsageHint } from "@/components/hints/usage-hint";
import { useActiveHint } from "@/context/usage-hints-context";

export default function LearnPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionParam = searchParams.get("session");
  const trialTopic = findTrialTopic(searchParams.get("trial"));
  const modeParam = searchParams.get("mode");
  const memoParam = searchParams.get("memo");
  const memoStartedRef = useRef<string | null>(null);
  const noteParam = searchParams.get("note");
  const feedbackParam = searchParams.get("feedback");
  const itemParam = searchParams.get("item");
  const improvementIndex =
    itemParam !== null && /^\d+$/.test(itemParam) ? Number(itemParam) : null;
  const improvementKey =
    noteParam && feedbackParam && improvementIndex !== null
      ? `${noteParam}:${feedbackParam}:${improvementIndex}`
      : null;
  const improvementStartedRef = useRef<string | null>(null);
  const [memoError, setMemoError] = useState<string | null>(null);
  const [exploreMode, setExploreMode] = useState(modeParam === "explore");
  const [topic, setTopic] = useState("");
  const [input, setInput] = useState("");
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [resumableSession, setResumableSession] =
    useState<ActiveSession | null>(null);
  const restoredSessionRef = useRef<string | null>(null);
  const trialStartedRef = useRef(false);
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
    endConfirmation,
    noteSkipped,
    dismissEndConfirmation,
    error,
    errorCode,
    editingMessage,
    editingRawTranscript,
    editingAutoSent,
    speechBus,
    sessionId,
    progress,
    sessionType,
    generatedStudyMemo,
    startExplore,
    sessionTopic,
    startLearning,
    resumeSession,
    sendMessage,
    editTopic,
    endSession,
    cancelLastMessage,
    clearEditingMessage,
    resetSession,
  } = useChatWebSocket({ draft: input });
  const isExplore =
    sessionType !== null ? sessionType === "explore" : exploreMode;
  useErrorToast(error);
  useErrorToast(memoError);
  const progressNotice = useProgressAdvanceNotice(progress);
  const [restoredTranscript, setRestoredTranscript] = useState<{
    text: string;
    autoSent: boolean;
  } | null>(null);

  useEffect(() => {
    if (!noteParam || !improvementKey) return;
    if (
      errorCode === "improvement_not_found" ||
      errorCode === "note_not_found"
    ) {
      router.replace(`/notes/${noteParam}`);
    }
  }, [errorCode, noteParam, improvementKey, router]);

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
          // 復習は復習ページ（復習バッジ・ノート更新ボタン）で再開する。
          if (sessionType === "review") {
            if (noteId) {
              router.replace(`/review/${noteId}?session=${sessionParam}`);
            }
            return;
          }
          setTopic(sessionTopicFromApi ?? messages[0]?.content ?? "");
          setExploreMode(sessionType === "explore");
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
    if (memoParam) {
      if (memoStartedRef.current === memoParam) return;
      memoStartedRef.current = memoParam;
      setExploreMode(false);
      setResumableSession(null);
      setIsBootstrapping(true);
      setMemoError(null);
      fetchAPI<StudyMemo>(`/api/study-memos/${memoParam}`)
        .then((memo) => {
          if (memoStartedRef.current !== memoParam) return;
          setTopic(memo.topic);
          startLearning(memo.topic, { study_memo_id: memo.id });
        })
        .catch(() => {
          memoStartedRef.current = null;
          setMemoError("学習メモを開けませんでした");
          router.replace("/learn");
        })
        .finally(() => setIsBootstrapping(false));
      return;
    }
    memoStartedRef.current = null;
    if (noteParam && feedbackParam && improvementIndex !== null) {
      if (improvementStartedRef.current === improvementKey) return;
      improvementStartedRef.current = improvementKey;
      setExploreMode(true);
      setResumableSession(null);
      setIsBootstrapping(false);
      startExplore("", {
        source: {
          note_id: noteParam,
          feedback_id: feedbackParam,
          improvement_index: improvementIndex,
        },
      });
      return;
    }
    improvementStartedRef.current = null;
    if (trialTopic) {
      if (trialStartedRef.current) return;
      trialStartedRef.current = true;
      setTopic(trialTopic.topic);
      setResumableSession(null);
      setIsBootstrapping(false);
      startLearning(trialTopic.topic, { trial: true });
      return;
    }
    trialStartedRef.current = false;
    resetSession();
    /* eslint-disable react-hooks/set-state-in-effect */
    setExploreMode(modeParam === "explore");
    setTopic("");
    setInput("");
    setRestoredTranscript(null);
    setIsBootstrapping(true);
    /* eslint-enable react-hooks/set-state-in-effect */
    fetchAPI<ActiveSession | null>("/api/dialogue-sessions/active")
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
  }, [
    sessionParam,
    modeParam,
    memoParam,
    noteParam,
    feedbackParam,
    improvementIndex,
    improvementKey,
    trialTopic,
    startExplore,
    resumeSession,
    resetSession,
    startLearning,
    router,
  ]);

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
    if (!generatedStudyMemo) return;
    router.push(`/study-memos/${generatedStudyMemo.id}`);
  }, [generatedStudyMemo, router]);

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

  const explanationCount =
    messages.filter(
      (m) =>
        m.role === "user" &&
        !m.intakeAnswered &&
        !m.topicEdit &&
        !m.topicCorrectionAnswered,
    ).length - 1;
  const dialogueStarted = (progress?.aspects?.length ?? 0) > 0;
  const chatHint = useActiveHint(
    isExplore
      ? []
      : [
          lastMessage?.intakeCard !== undefined &&
            !isSessionEnded &&
            "intake_card",
          !isSessionEnded && explanationCount < 1 && "chat_input",
          dialogueStarted &&
            !isSessionEnded &&
            !isLoading &&
            !choicePending &&
            explanationCount >= 1 &&
            "dialogue",
          dialogueStarted &&
            !isSessionEnded &&
            !isLoading &&
            !choicePending &&
            ((progress?.reached_aspects.length ?? 0) > 0 ||
              explanationCount >= 3) &&
            "end_session",
        ],
  );

  const displayTopic = sessionTopic ?? topic;
  const canEditTopic =
    isConnected &&
    !isLoading &&
    !isSessionEnded &&
    (progress?.aspects?.length ?? 0) > 0;
  const isChatVisible = isConnected || messages.length > 0;

  useEffect(() => {
    if (isChatVisible && displayTopic) {
      setNavbarCenter(
        <SessionHeader
          topic={displayTopic}
          onEditTopic={canEditTopic ? editTopic : undefined}
          progress={progress}
          progressHighlighted={progressNotice !== null}
          progressOpen={progressPanel.open}
          onProgressOpenChange={progressPanel.setOpen}
          notice={progressNotice}
          isReconnecting={isReconnecting}
          endLabel={isExplore ? "学習メモを作成" : "ノートを作成"}
          endHighlighted={isExplore ? false : (progress?.is_complete ?? false)}
          onEnd={endSession}
        />,
      );
    } else {
      setNavbarCenter(null);
    }
    return () => setNavbarCenter(null);
  }, [
    isChatVisible,
    isReconnecting,
    displayTopic,
    canEditTopic,
    editTopic,
    progress,
    isExplore,
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
    const voiceOptions = rawTranscript
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
      : undefined;
    if (exploreMode) {
      startExplore(utterance, voiceOptions);
      return;
    }
    startLearning(utterance, voiceOptions);
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
          <div className="flex-1 overflow-y-auto px-4 md:px-6">
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

  const resumableHref = resumableSession
    ? activeSessionHref(resumableSession)
    : null;

  if (messages.length === 0 && !isConnected) {
    return (
      <div className="flex h-full flex-col items-center overflow-y-auto p-4">
        <div className="my-4 flex w-full max-w-2xl flex-1 flex-col gap-4">
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
                  <SessionTypeBadge type={resumableSession.session_type} />
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
          <div className="space-y-8 pt-4 md:my-auto">
            <h1 className="flex flex-col items-center justify-center gap-2 text-2xl font-bold tracking-tight text-foreground">
              <AppLogo className="h-8" />
              何を学びますか？
            </h1>
            <div>
              <UsageHint id="learn_start" className="mb-3" />
              <StartModeToggle
                explore={exploreMode}
                onChange={setExploreMode}
              />
              {conversation.status !== "off" ? (
                <VoicePanel
                  status={conversation.status}
                  segments={conversation.segments}
                  speed={conversation.speed}
                  noInterrupt={conversation.noInterrupt}
                  holdForReview={false}
                  subscribeLevel={conversation.subscribeLevel}
                  onSpeedChange={conversation.setSpeed}
                  onNoInterruptChange={conversation.setNoInterrupt}
                  onStopSpeech={conversation.stopSpeech}
                  onPause={conversation.pause}
                  onResume={conversation.resume}
                  onSendNow={() => void conversation.sendNow()}
                  onDiscard={conversation.discard}
                  onEnd={conversation.stop}
                  onBeginEdit={conversation.beginEdit}
                  onSubmitEdit={conversation.sendEdited}
                  onCancelEdit={() => void conversation.cancelEdit()}
                />
              ) : (
                <ChatInput
                  value={input}
                  onChange={setInput}
                  onSend={(content, _images, rawTranscript, autoSent) =>
                    handleStartLearning(content, rawTranscript, autoSent)
                  }
                  isLoading={false}
                  placeholder={
                    exploreMode
                      ? "学びたいこと（まだ何も知らなくて大丈夫です）"
                      : "学びたいこと、目的や状況を書いてください"
                  }
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
      <div className="flex-1 overflow-y-auto px-4 md:px-6">
        <div className="mx-auto max-w-3xl space-y-4 py-6">
          {messages.map((msg, i) => {
            if (i === 0 && msg.role === "user" && !isExplore) return null;
            if (msg.role === "user" && msg.intakeAnswered) {
              return (
                <IntakeAnsweredNotice
                  key={i}
                  onOpenPanel={isExplore ? undefined : progressPanel.openPanel}
                />
              );
            }
            if (msg.role === "user" && msg.topicEdit) {
              return <TopicEditedNotice key={i} content={msg.content} />;
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
                className={`group flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}
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
                      {closeOpenBlocks(msg.content, {
                        streaming: isLoading && i === messages.length - 1,
                      })}
                    </Markdown>
                  )}
                  {endConfirmation &&
                    msg.role === "assistant" &&
                    i === messages.length - 1 &&
                    !isLoading &&
                    !isSessionEnded && (
                      <EndSessionConfirm
                        kind={isExplore ? "explore" : "learning"}
                        createsNote={endConfirmation.creates_note}
                        progress={
                          isExplore || !progress
                            ? null
                            : {
                                reached: progress.reached_aspects.length,
                                target: progress.target_count,
                              }
                        }
                        onEnd={endSession}
                        onContinue={dismissEndConfirmation}
                      />
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
                  {activeIntakeCard && chatHint === "intake_card" && (
                    <UsageHint id="intake_card" className="mt-3" />
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
                <div className="flex items-center gap-1">
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

          {(chatHint === "dialogue" || chatHint === "end_session") && (
            <UsageHint id={chatHint} />
          )}

          {isSessionEnded &&
            !generatedNote &&
            !generatedStudyMemo &&
            !isGeneratingNote && (
              <SessionEndedNotice
                kind={isExplore ? "explore" : "learning"}
                noteSkipped={noteSkipped}
              />
            )}

          <div ref={bottomRef} />
        </div>
      </div>

      {!isSessionEnded && (
        <div className="shrink-0 bg-background/95 px-4 pt-4 pb-[max(1rem,env(safe-area-inset-bottom))] backdrop-blur-sm md:px-6 md:pb-4">
          <div className="mx-auto max-w-3xl">
            {chatHint === "chat_input" && (
              <UsageHint id="chat_input" className="mb-3" />
            )}
            {conversation.status !== "off" ? (
              <VoicePanel
                status={conversation.status}
                segments={conversation.segments}
                speed={conversation.speed}
                noInterrupt={conversation.noInterrupt}
                holdForReview={choicePending}
                subscribeLevel={conversation.subscribeLevel}
                onSpeedChange={conversation.setSpeed}
                onNoInterruptChange={conversation.setNoInterrupt}
                onStopSpeech={conversation.stopSpeech}
                onPause={conversation.pause}
                onResume={conversation.resume}
                onSendNow={() => void conversation.sendNow()}
                onDiscard={conversation.discard}
                onEnd={conversation.stop}
                onBeginEdit={conversation.beginEdit}
                onSubmitEdit={conversation.sendEdited}
                onCancelEdit={() => void conversation.cancelEdit()}
              />
            ) : (
              <ChatInput
                value={input}
                onChange={setInput}
                onSend={handleSendMessage}
                isLoading={isLoading}
                sessionId={sessionId}
                transcriptionTopic={sessionTopic ?? (topic || null)}
                allowVoice
                allowRichInput
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

      {isGeneratingNote && (
        <LoadingOverlay
          message={isExplore ? "学習メモ作成中..." : "ノート作成中..."}
        />
      )}
    </div>
  );
}
