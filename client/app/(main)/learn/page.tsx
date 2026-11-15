"use client";

import { LoadingOverlay } from "@/components/ui/loading-overlay";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useChatWebSocket, type VoiceMeta } from "@/hooks/use-chat-websocket";
import {
  draftKey,
  removeDraft,
  usePersistedDraft,
} from "@/hooks/use-persisted-draft";
import { useErrorToast } from "@/hooks/use-error-toast";
import { useLeaveSession } from "@/hooks/use-leave-session";
import {
  useVoiceConversation,
  type VoiceUtterance,
} from "@/hooks/use-voice-conversation";
import { fetchAPI } from "@/lib/api";
import {
  ENDED_SESSION_MESSAGE,
  isUnresumableErrorCode,
  loadResumableMessages,
  isResumableStatus,
} from "@/lib/session";
import type { PreparedImage } from "@/lib/image";
import { useNavbarSlot } from "@/context/navbar-slot-context";
import { Skeleton } from "@/components/ui/skeleton";
import { ChatInput } from "@/components/chat/chat-input";
import { EndSessionDialog } from "@/components/chat/end-session-dialog";
import { toast } from "sonner";
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
import { StartQuestionsButton } from "@/components/chat/start-questions-button";
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
import { canStopGeneration } from "@/lib/stop-generation";
import { EditResendButton } from "@/components/chat/edit-resend-button";
import { HintHelp } from "@/components/hints/hint-help";
import { PageHelpSlot } from "@/components/hints/page-help-slot";
import { UsageHint } from "@/components/hints/usage-hint";
import { useActiveHint } from "@/context/usage-hints-context";
import type { HintId } from "@/lib/hints";
import { useCoarsePointer } from "@/hooks/use-coarse-pointer";
import { useSideQuestions } from "@/hooks/use-side-questions";
import { draftAsThread, type SideDraft } from "@/lib/side-question-tree";
import {
  SelectionAskButton,
  type SelectedPassage,
} from "@/components/chat/side-questions/selection-ask-button";
import { SideQuestionPanel } from "@/components/chat/side-questions/side-question-panel";
import {
  AnchorHighlights,
  type HighlightAnchor,
} from "@/components/chat/side-questions/anchor-highlights";
import type { SideThreadView } from "@/components/chat/side-questions/side-question-card";

const LEARNING_HELP_HINTS: readonly HintId[] = [
  "intake_card",
  "dialogue",
  "chat_input",
  "end_session",
];

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
  const [voicePersist, setVoicePersist] = useState<string | undefined>();
  const [voiceEditDraft, setVoiceEditDraft] = useState<string | null>(null);
  const [startedSessionId, setStartedSessionId] = useState<string | null>(null);
  const draftSessionId = sessionParam ?? startedSessionId;
  const [input, setInput] = usePersistedDraft(
    draftSessionId
      ? draftKey.session(draftSessionId)
      : draftKey.start(exploreMode ? "explore" : "learning"),
    voicePersist,
  );
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [endDialogOpen, setEndDialogOpen] = useState(false);
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
    pendingQuestions,
    startQuestions,
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
    isCancelling,
    clearEditingMessage,
    resetSession,
    disconnect,
  } = useChatWebSocket({ draft: input });

  const sessionIdRef = useRef<string | null>(null);
  useEffect(() => {
    sessionIdRef.current = sessionId;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStartedSessionId(sessionId);
  }, [sessionId]);
  const isExplore =
    sessionType !== null ? sessionType === "explore" : exploreMode;
  const coarsePointer = useCoarsePointer();
  const sideEnabled = isExplore && !coarsePointer;
  const side = useSideQuestions(sideEnabled ? sessionId : null, sideEnabled);
  const [sideHoverId, setSideHoverId] = useState<string | null>(null);
  const [sideFocusId, setSideFocusId] = useState<string | null>(null);
  const [sidePanelClosed, setSidePanelClosed] = useState(false);
  const removeSideByAnchorMessage = side.removeByAnchorMessage;
  const previousMessagesRef = useRef(messages);
  useEffect(() => {
    const previous = previousMessagesRef.current;
    previousMessagesRef.current = messages;
    if (messages.length >= previous.length) return;
    const kept = new Set(messages.map((m) => m.id));
    for (const m of previous) {
      if (m.role === "assistant" && m.id && !kept.has(m.id)) {
        removeSideByAnchorMessage(m.id);
      }
    }
  }, [messages, removeSideByAnchorMessage]);
  const sideThreads = useMemo(
    () =>
      side.draft ? [...side.threads, draftAsThread(side.draft)] : side.threads,
    [side.threads, side.draft],
  );
  const sideAnchors = useMemo<HighlightAnchor[]>(
    () =>
      sideThreads.map((t) => ({
        id: t.id,
        rootSelector: t.anchorMessageId
          ? `[data-message-id="${t.anchorMessageId}"]`
          : `[data-side-message-id="${t.anchorSideMessageId}"]`,
        quote: t.quote,
        occurrence: t.occurrence,
      })),
    [sideThreads],
  );
  useErrorToast(error);
  useErrorToast(memoError);
  useErrorToast(
    side.loadFailed ? "これまでの質問を読み込めませんでした" : null,
    { label: "再読み込み", onClick: side.reload },
  );
  const discardDestination = useCallback(() => {
    resetSession();
    router.replace("/learn");
  }, [resetSession, router]);
  const endAndClose = () => {
    const ok = endSession();
    if (ok !== false) setEndDialogOpen(false);
    return ok;
  };
  const leave = useLeaveSession(sessionId, discardDestination, disconnect);
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
      if (sessionIdRef.current && sessionIdRef.current !== sessionParam) {
        resetSession();
      }
      setIsBootstrapping(true);

      (async () => {
        try {
          const {
            sessionType,
            status,
            noteId,
            messages,
            topic: sessionTopicFromApi,
          } = await loadResumableMessages(sessionParam);
          if (!isResumableStatus(status)) {
            toast.info(ENDED_SESSION_MESSAGE);
            router.replace("/learn");
            return;
          }
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
      setIsBootstrapping(false);
      setTopic(trialTopic.topic);
      startLearning(trialTopic.topic, { trial: true });
      return;
    }
    trialStartedRef.current = false;
    resetSession();
    /* eslint-disable react-hooks/set-state-in-effect */
    setExploreMode(modeParam === "explore");
    setTopic("");
    setRestoredTranscript(null);
    setIsBootstrapping(false);
    /* eslint-enable react-hooks/set-state-in-effect */
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
    if (!sessionParam || !isUnresumableErrorCode(errorCode)) return;
    toast.info(ENDED_SESSION_MESSAGE);
    resetSession();
    router.replace("/learn");
  }, [errorCode, sessionParam, resetSession, router]);

  const prevStartedSessionIdRef = useRef<string | null>(null);
  useEffect(() => {
    const startedFresh =
      startedSessionId && !prevStartedSessionIdRef.current && !sessionParam;
    prevStartedSessionIdRef.current = startedSessionId;
    if (!startedFresh) return;
    removeDraft(draftKey.start("learning"));
    removeDraft(draftKey.start("explore"));
  }, [startedSessionId, sessionParam]);

  useEffect(() => {
    if (!sessionId) return;
    if (sessionParam === sessionId) return;
    if (sessionParam && restoredSessionRef.current === sessionParam) return;
    restoredSessionRef.current = sessionId;
    router.replace(`/learn?session=${sessionId}`);
  }, [sessionId, sessionParam, router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    if (isSessionEnded) setInput("");
  }, [isSessionEnded, setInput]);

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
  const firstAnswerShown = messages.some(
    (m) => m.role === "assistant" && m.id !== undefined,
  );
  const chatHint = useActiveHint(
    isExplore
      ? [
          sideEnabled &&
            firstAnswerShown &&
            !isSessionEnded &&
            "explore_side_question",
        ]
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
          endLabel="終了する"
          endHighlighted={isExplore ? false : (progress?.is_complete ?? false)}
          onEnd={() => setEndDialogOpen(true)}
          helpIds={isExplore ? undefined : LEARNING_HELP_HINTS}
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
    setTopic(utterance);
    setInput("");
    setRestoredTranscript(null);
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
  const voiceStatus = conversation.status;
  const voiceUnsent = conversation.unsentText;
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setVoicePersist(
      voiceStatus === "off"
        ? undefined
        : (voiceEditDraft ?? voiceUnsent) || undefined,
    );
  }, [voiceStatus, voiceEditDraft, voiceUnsent]);
  useErrorToast(conversation.error);
  useErrorToast(conversation.speechError);
  const canStop =
    canStopGeneration(messages, isLoading, 1) &&
    !isSessionEnded &&
    !isGeneratingNote;
  const handleCancel = () => {
    conversation.stop();
    cancelLastMessage();
  };
  const stopConversation = conversation.stop;

  useEffect(() => {
    if (isSessionEnded) stopConversation();
  }, [isSessionEnded, stopConversation]);

  const previousSessionParamRef = useRef(sessionParam);
  useEffect(() => {
    if (previousSessionParamRef.current && !sessionParam) stopConversation();
    previousSessionParamRef.current = sessionParam;
  }, [sessionParam, stopConversation]);

  const openSideThread = (id: string) => {
    setSidePanelClosed(false);
    setSideFocusId(id);
    side.openThread(id);
  };
  const toggleSideThread = (id: string) => {
    setSideFocusId(side.open.has(id) ? null : id);
    side.toggle(id);
  };
  const askAboutPassage = ({ root, quote, occurrence }: SelectedPassage) => {
    const { messageId, sideMessageId, sideThreadId, sideDepth } = root.dataset;
    const tempId = `draft-${crypto.randomUUID()}`;
    let draft: SideDraft;
    if (messageId) {
      draft = {
        tempId,
        parentId: null,
        anchor: { anchorMessageId: messageId },
        quote,
        occurrence,
        depth: 0,
      };
    } else if (sideMessageId && sideThreadId) {
      draft = {
        tempId,
        parentId: sideThreadId,
        anchor: { anchorSideMessageId: sideMessageId },
        quote,
        occurrence,
        depth: Number(sideDepth ?? 0) + 1,
      };
    } else {
      return;
    }
    setSidePanelClosed(false);
    setSideFocusId(tempId);
    side.startDraft(draft);
  };
  const sideView: SideThreadView = {
    threads: sideThreads,
    open: side.open,
    streaming: side.streaming,
    error: side.error,
    focusId: sideFocusId,
    draftId: side.draft?.tempId ?? null,
    onToggle: toggleSideThread,
    onSend: (id, content) => void side.send(id, content),
    onHover: setSideHoverId,
  };
  const sideActive = sideEnabled && !isSessionEnded;
  const showSidePanel = sideActive && sideThreads.length > 0;

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

  if (messages.length === 0 && !isConnected) {
    return (
      <div className="flex h-full flex-col items-center overflow-y-auto p-4">
        <div className="my-4 flex w-full max-w-2xl flex-1 flex-col gap-4">
          <PageHelpSlot ids={["learn_start"]} />
          <div className="flex justify-end max-md:hidden">
            <HintHelp ids={["learn_start"]} />
          </div>
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
                  onContinueEdit={conversation.continueEdited}
                  editedPrefix={conversation.editedPrefix}
                  onEditDraftChange={setVoiceEditDraft}
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
    <div className="relative flex h-full">
      <div className="flex h-full min-w-0 flex-1 flex-col">
        <div className="flex-1 overflow-y-auto px-4 md:px-6">
          <div className="mx-auto max-w-3xl space-y-4 py-6">
            {messages.map((msg, i) => {
              if (i === 0 && msg.role === "user" && !isExplore) return null;
              if (msg.role === "user" && msg.intakeAnswered) {
                return (
                  <IntakeAnsweredNotice
                    key={i}
                    onOpenPanel={
                      isExplore ? undefined : progressPanel.openPanel
                    }
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
                      <div
                        data-message-id={
                          msg.role === "assistant" ? msg.id : undefined
                        }
                        data-side-selectable={
                          sideActive &&
                          msg.role === "assistant" &&
                          msg.id &&
                          !(isLoading && i === messages.length - 1)
                            ? ""
                            : undefined
                        }
                      >
                        <Markdown
                          variant="chat"
                          className="[&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
                        >
                          {closeOpenBlocks(msg.content, {
                            streaming: isLoading && i === messages.length - 1,
                          })}
                        </Markdown>
                      </div>
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
                          onSave={leave.onSave}
                          onDiscard={leave.onDiscard}
                        />
                      )}
                    {!endConfirmation &&
                      !activeTopicCorrection &&
                      !activeIntakeCard &&
                      !isExplore &&
                      pendingQuestions !== null &&
                      pendingQuestions > 0 &&
                      msg.role === "assistant" &&
                      i === messages.length - 1 &&
                      !isLoading &&
                      !isSessionEnded && (
                        <StartQuestionsButton
                          count={pendingQuestions}
                          onStart={startQuestions}
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
                      <EditResendButton onClick={handleCancel} />
                    )}
                  </div>
                </div>
              );
            })}

            {isLoading &&
              messages[messages.length - 1]?.role !== "assistant" && (
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
              {chatHint === "explore_side_question" && (
                <UsageHint
                  id="explore_side_question"
                  className="mb-3 max-md:hidden"
                />
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
                  onContinueEdit={conversation.continueEdited}
                  editedPrefix={conversation.editedPrefix}
                  onEditDraftChange={setVoiceEditDraft}
                  onStopGeneration={handleCancel}
                  canStopGeneration={canStop}
                  isStoppingGeneration={isCancelling}
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
                  onStop={handleCancel}
                  canStop={canStop}
                  isStopping={isCancelling}
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
      {showSidePanel && (
        <SideQuestionPanel
          view={sideView}
          messageOrder={messages.flatMap((m) =>
            m.role === "assistant" && m.id ? [m.id] : [],
          )}
          overlayClosed={sidePanelClosed}
          onFoldAll={side.foldAll}
          onCloseOverlay={() => setSidePanelClosed(true)}
        />
      )}
      {sideActive && <SelectionAskButton onAsk={askAboutPassage} />}
      <EndSessionDialog
        open={endDialogOpen}
        onOpenChange={setEndDialogOpen}
        kind={isExplore ? "explore" : "learning"}
        topic={displayTopic}
        progress={
          isExplore || !progress
            ? null
            : {
                reached: progress.reached_aspects.length,
                target: progress.target_count,
              }
        }
        onEnd={endAndClose}
        onSave={leave.onSave}
        onDiscard={leave.onDiscard}
      />
      {sideActive && (
        <AnchorHighlights
          anchors={sideAnchors}
          hoverId={sideHoverId}
          openIds={side.open}
          onOpen={openSideThread}
        />
      )}
    </div>
  );
}
