"use client";

import { LoadingOverlay } from "@/components/ui/loading-overlay";
import { useRef, useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useChatWebSocket, type VoiceMeta } from "@/hooks/use-chat-websocket";
import { useErrorToast } from "@/hooks/use-error-toast";
import {
  useVoiceConversation,
  type VoiceUtterance,
} from "@/hooks/use-voice-conversation";
import { useNavbarSlot } from "@/context/navbar-slot-context";
import { fetchAPI } from "@/lib/api";
import { loadResumableMessages, isResumableStatus } from "@/lib/session";
import type { PreparedImage } from "@/lib/image";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ChatInput } from "@/components/chat/chat-input";
import { ReconnectingIndicator } from "@/components/chat/reconnecting-indicator";
import { VoicePanel } from "@/components/chat/voice-panel";
import { MessageSpeechButton } from "@/components/chat/message-speech-button";
import { TypingIndicator } from "@/components/chat/typing-indicator";
import { Badge } from "@/components/ui/badge";
import { Markdown } from "@/components/ui/markdown";
import {
  ArrowLeftIcon,
  NotebookPenIcon,
  RotateCcwIcon,
  SparklesIcon,
  PencilIcon,
} from "lucide-react";

interface Note {
  id: string;
  topic: string;
  content: string;
  summary: string;
}

export default function ReviewPage({
  params,
}: {
  params: Promise<{ noteId: string }>;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionParam = searchParams.get("session");
  const { noteId } = use(params);
  const [note, setNote] = useState<Note | null>(null);
  const [input, setInput] = useState("");
  const [isReviewStarted, setIsReviewStarted] = useState(false);
  // session 付きで開いた場合は再開フローに入るため、開始画面のチラつきを避けて最初から再開中にする。
  const [isBootstrapping, setIsBootstrapping] = useState(Boolean(sessionParam));
  const [loadError, setLoadError] = useState<string | null>(null);
  const restoredSessionRef = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { setNavbarCenter } = useNavbarSlot();

  const {
    messages,
    isReconnecting,
    isLoading,
    isSessionEnded,
    isGeneratingNote,
    feedback,
    error,
    editingMessage,
    editingRawTranscript,
    editingAutoSent,
    speechBus,
    sessionId,
    startReview,
    resumeSession,
    sendMessage,
    endSession,
    cancelLastMessage,
    clearEditingMessage,
  } = useChatWebSocket();
  useErrorToast(error);
  const [restoredTranscript, setRestoredTranscript] = useState<{
    text: string;
    autoSent: boolean;
  } | null>(null);

  useEffect(() => {
    fetchAPI<Note>(`/api/notes/${noteId}`)
      .then(setNote)
      .catch((e) => setLoadError(e.message));
  }, [noteId]);

  useEffect(() => {
    if (!sessionParam) return;
    if (restoredSessionRef.current === sessionParam) return;
    restoredSessionRef.current = sessionParam;
    setIsBootstrapping(true);

    (async () => {
      try {
        const { sessionType, status, messages } =
          await loadResumableMessages(sessionParam);
        if (sessionType !== "review" || !isResumableStatus(status)) {
          router.replace(`/review/${noteId}`);
          return;
        }
        // 先頭はノートのトピック。ヘッダに表示済みのためチャットからは除外する（learning と対称）。
        resumeSession(sessionParam, messages.slice(1));
        setIsReviewStarted(true);
      } catch {
        router.replace(`/review/${noteId}`);
      } finally {
        setIsBootstrapping(false);
      }
    })();
  }, [sessionParam, noteId, resumeSession, router]);

  useEffect(() => {
    if (!feedback) return;
    router.push(`/notes/${noteId}`);
  }, [feedback, noteId, router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (editingMessage !== null) {
    setInput(editingMessage);
    setRestoredTranscript(
      editingRawTranscript
        ? { text: editingRawTranscript, autoSent: editingAutoSent }
        : null,
    );
    clearEditingMessage();
  }

  useEffect(() => {
    if (isReviewStarted && note) {
      setNavbarCenter(
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <RotateCcwIcon className="size-4 text-primary shrink-0" />
            <h1 className="text-sm font-semibold">{note.topic}</h1>
            <Badge variant="warning" className="text-xs">
              復習
            </Badge>
          </div>
          <div className="h-4 w-px bg-border" />
          {isReconnecting && <ReconnectingIndicator />}
          <div className="flex items-center gap-1">
            <div className="group relative">
              <Button
                variant="ghost"
                size="icon"
                onClick={endSession}
                className="size-8 rounded-full"
              >
                <NotebookPenIcon className="size-4.5" />
              </Button>
              <span className="pointer-events-none absolute top-full left-1/2 mt-1 -translate-x-1/2 whitespace-nowrap rounded-md border bg-popover px-2 py-1 text-xs opacity-0 shadow-sm transition-opacity group-hover:opacity-100">
                ノート更新
              </span>
            </div>
          </div>
        </div>,
      );
    } else {
      setNavbarCenter(null);
    }
    return () => setNavbarCenter(null);
  }, [
    isReviewStarted,
    isReconnecting,
    note,
    endSession,
    router,
    setNavbarCenter,
  ]);

  const handleStartReview = () => {
    if (!note) return;
    setIsReviewStarted(true);
    startReview(noteId);
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
    holdForReview: false,
    topic: note?.topic ?? null,
    onSend: (u) =>
      handleSendMessage(
        u.content,
        undefined,
        u.rawTranscript,
        true,
        voiceMeta(u),
      ),
    onHold: (u) => {
      setInput(u.content);
      setRestoredTranscript({ text: u.rawTranscript, autoSent: false });
    },
  });
  useErrorToast(conversation.error);
  useErrorToast(conversation.speechError);
  const stopConversation = conversation.stop;

  useEffect(() => {
    if (isSessionEnded) stopConversation();
  }, [isSessionEnded, stopConversation]);

  if (loadError) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-destructive">{loadError}</p>
      </div>
    );
  }

  if (isBootstrapping) {
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

  if (!note) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-8 space-y-6">
        <Skeleton className="h-4 w-24" />
        <div className="flex items-center gap-3 mb-8">
          <Skeleton className="size-10 rounded-lg" />
          <div className="space-y-1">
            <Skeleton className="h-8 w-24" />
            <Skeleton className="h-4 w-48" />
          </div>
        </div>
        <div className="space-y-3">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="size-4/5" />
        </div>
      </div>
    );
  }

  if (!isReviewStarted) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-8">
        <Link
          href={`/notes/${noteId}`}
          className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeftIcon className="size-4" />
          ノートに戻る
        </Link>

        <div className="mb-8 flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10">
            <RotateCcwIcon className="size-5 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">復習</h1>
            <p className="text-sm text-muted-foreground">{note.topic}</p>
          </div>
        </div>

        <div className="mb-8 rounded-xl border bg-card p-6">
          <div className="mb-3 flex items-center gap-2">
            <SparklesIcon className="size-4 text-primary" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-primary">
              前回の要約
            </h2>
          </div>
          <Markdown>{note.summary}</Markdown>
        </div>

        <Button onClick={handleStartReview} size="lg" className="w-full gap-2">
          <RotateCcwIcon className="size-5" />
          復習を開始する
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-6">
        <div className="mx-auto max-w-3xl space-y-4 py-6">
          {messages.map((msg, i) => {
            const isLastUserMessage =
              msg.role === "user" &&
              i === messages.length - 2 &&
              messages.length >= 4 &&
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
                  className={`max-w-full rounded-2xl px-4 py-3 text-base leading-relaxed whitespace-pre-wrap ${
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
                  {msg.content}
                </div>
                {canSpeak && speechKey && (
                  <MessageSpeechButton
                    speaking={conversation.activeKey === speechKey}
                    onPlay={() =>
                      conversation.playMessage(speechKey, msg.content)
                    }
                    onStop={conversation.stopSpeech}
                  />
                )}
                {isLastUserMessage && (
                  <button
                    type="button"
                    onClick={() => {
                      conversation.stop();
                      cancelLastMessage();
                    }}
                    className="mt-2 cursor-pointer opacity-0 transition-opacity group-hover:opacity-100"
                    title="編集して再送信"
                  >
                    <PencilIcon className="size-4 text-muted-foreground hover:text-foreground" />
                  </button>
                )}
              </div>
            );
          })}

          {isLoading && messages[messages.length - 1]?.role !== "assistant" && (
            <TypingIndicator />
          )}

          {isSessionEnded && !feedback && !isGeneratingNote && (
            <div className="mx-auto max-w-md rounded-xl border bg-card p-6 text-center">
              <p className="text-sm text-muted-foreground">
                復習セッションが終了しました
              </p>
              <Button asChild variant="link" className="mt-2">
                <Link href={`/notes/${noteId}`}>ノートに戻る</Link>
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
                holdForReview={false}
                timings={conversation.timings}
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

      {isGeneratingNote && <LoadingOverlay message="ノート更新中..." />}
    </div>
  );
}
