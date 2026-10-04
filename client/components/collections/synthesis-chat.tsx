"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeftIcon, PencilIcon } from "lucide-react";

import { Spinner } from "@/components/ui/spinner";
import { useChatWebSocket } from "@/hooks/use-chat-websocket";
import { useErrorToast } from "@/hooks/use-error-toast";
import { Button } from "@/components/ui/button";
import { ChatInput } from "@/components/chat/chat-input";
import { TypingIndicator } from "@/components/chat/typing-indicator";
import { Markdown } from "@/components/ui/markdown";

export function SynthesisChat({
  collectionId,
  collectionName,
}: {
  collectionId: string;
  collectionName: string;
}) {
  const router = useRouter();
  const [input, setInput] = useState("");
  const [isStarted, setIsStarted] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const {
    messages,
    isLoading,
    isSessionEnded,
    isGeneratingNote,
    isSynthesisSaved,
    error,
    editingMessage,
    startSynthesis,
    sendMessage,
    endSession,
    cancelLastMessage,
    clearEditingMessage,
  } = useChatWebSocket();
  useErrorToast(error && !isSessionEnded ? error : null);

  useEffect(() => {
    if (isSynthesisSaved) router.push(`/collections/${collectionId}#synthesis`);
  }, [isSynthesisSaved, collectionId, router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (editingMessage !== null) {
    setInput(editingMessage);
    clearEditingMessage();
  }

  const isSaveFailed = isSessionEnded && error !== null;

  const backLink = (
    <Link
      href={`/collections/${collectionId}`}
      className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeftIcon className="size-4" />
      まとめノートに戻る
    </Link>
  );

  if (!isStarted) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-8">
        {backLink}
        <h1 className="mb-2 text-2xl font-bold">つながりを説明する</h1>
        <p className="mb-8 text-sm text-muted-foreground">
          「{collectionName}」のノートどうしのつながりを、3つまで順に聞きます。
          説明はまとめに追記されます。
        </p>
        <Button
          size="lg"
          className="w-full"
          onClick={() => {
            setIsStarted(true);
            startSynthesis(collectionId);
          }}
        >
          説明を始める
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
              messages.length >= 3 &&
              !isLoading &&
              !isSessionEnded;
            return (
              <div
                key={i}
                className={`group flex items-start gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
              >
                <div
                  className={`max-w-full rounded-2xl px-4 py-3 ${msg.role === "user" ? "bg-muted whitespace-pre-wrap" : ""}`}
                >
                  {msg.role === "assistant" ? (
                    <Markdown variant="chat">{msg.content}</Markdown>
                  ) : (
                    msg.content
                  )}
                </div>
                {isLastUserMessage && (
                  <button
                    type="button"
                    onClick={cancelLastMessage}
                    className="mt-2 cursor-pointer opacity-0 transition-opacity group-hover:opacity-100"
                    title="編集して再送信"
                  >
                    <PencilIcon className="size-4 text-muted-foreground hover:text-foreground" />
                  </button>
                )}
              </div>
            );
          })}
          {isLoading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>
      </div>
      <div className="border-t p-4">
        <div className="mx-auto flex max-w-3xl flex-col gap-3">
          {isSaveFailed ? (
            <div className="flex flex-col gap-2 text-sm">
              <p className="text-destructive">説明の反映に失敗しました。</p>
              <Link
                href={`/collections/${collectionId}`}
                className="text-muted-foreground underline hover:text-foreground"
              >
                まとめノートに戻る
              </Link>
            </div>
          ) : isSessionEnded || isGeneratingNote ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner />
              説明をまとめに反映しています
            </p>
          ) : (
            <>
              <ChatInput
                value={input}
                onChange={setInput}
                onSend={(content) => {
                  if (!content.trim()) return;
                  sendMessage(content);
                  setInput("");
                }}
                isLoading={isLoading}
                allowImages={false}
                placeholder="つながりを自分の言葉で説明してください"
              />
              <Button
                variant="outline"
                onClick={endSession}
                disabled={isLoading}
              >
                終了してまとめに反映する
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
