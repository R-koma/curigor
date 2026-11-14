"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import {
  closeWithDescendants,
  descendantsOf,
  draftAsThread,
  openOnly,
  type SideDraft,
} from "@/lib/side-question-tree";
import {
  fetchSideQuestions,
  streamNewSideQuestion,
  streamSideFollowUp,
  type SideQuestion,
  type SideStreamEvent,
} from "@/lib/side-questions";

export interface SideStreaming {
  sideQuestionId: string;
  question: string;
  text: string;
}

export interface SideError {
  id: string;
  detail: string;
  content: string;
}

const FAILED_DETAIL = "回答を作れませんでした。もう一度送ってください";

function withDraft(threads: SideQuestion[], draft: SideDraft | null) {
  return draft ? [...threads, draftAsThread(draft)] : threads;
}

export function useSideQuestions(sessionId: string | null, enabled: boolean) {
  const [threads, setThreads] = useState<SideQuestion[]>([]);
  const [draft, setDraft] = useState<SideDraft | null>(null);
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const [streaming, setStreaming] = useState<SideStreaming | null>(null);
  const [error, setError] = useState<SideError | null>(null);

  const threadsRef = useRef(threads);
  const draftRef = useRef(draft);
  const openRef = useRef(open);
  const streamingRef = useRef(streaming);
  const abortRef = useRef<AbortController | null>(null);
  useEffect(() => {
    threadsRef.current = threads;
    draftRef.current = draft;
    openRef.current = open;
    streamingRef.current = streaming;
  });

  useEffect(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setThreads((threadsRef.current = []));
    setDraft((draftRef.current = null));
    setOpen((openRef.current = new Set()));
    setStreaming((streamingRef.current = null));
    setError(null);
    if (!sessionId || !enabled) return;
    let active = true;
    fetchSideQuestions(sessionId).then(
      (loaded) => {
        if (active) setThreads((threadsRef.current = loaded));
      },
      () => {},
    );
    return () => {
      active = false;
    };
  }, [sessionId, enabled]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const applyOpen = useCallback((next: Set<string>) => {
    const current = draftRef.current;
    if (current && !next.has(current.tempId) && !streamingRef.current) {
      setDraft((draftRef.current = null));
    }
    setOpen((openRef.current = next));
  }, []);

  const startDraft = useCallback((next: SideDraft) => {
    setDraft((draftRef.current = next));
    setError(null);
    setOpen(
      (openRef.current = openOnly(
        withDraft(threadsRef.current, next),
        next.tempId,
      )),
    );
  }, []);

  const openThread = useCallback(
    (id: string) => {
      applyOpen(openOnly(withDraft(threadsRef.current, draftRef.current), id));
    },
    [applyOpen],
  );

  const toggle = useCallback(
    (id: string) => {
      const all = withDraft(threadsRef.current, draftRef.current);
      applyOpen(
        openRef.current.has(id)
          ? closeWithDescendants(all, openRef.current, id)
          : openOnly(all, id),
      );
    },
    [applyOpen],
  );

  const foldAll = useCallback(() => applyOpen(new Set()), [applyOpen]);

  const removeByAnchorMessage = useCallback((messageId: string) => {
    const all = withDraft(threadsRef.current, draftRef.current);
    const removed = new Set<string>();
    for (const t of all) {
      if (t.anchorMessageId === messageId) {
        for (const id of descendantsOf(all, t.id)) removed.add(id);
      }
    }
    if (removed.size === 0) return;
    setThreads((current) => current.filter((t) => !removed.has(t.id)));
    if (draftRef.current && removed.has(draftRef.current.tempId)) {
      setDraft((draftRef.current = null));
    }
    setOpen(
      (current) => new Set([...current].filter((id) => !removed.has(id))),
    );
  }, []);

  const send = useCallback(
    async (id: string, content: string) => {
      const text = content.trim();
      if (streamingRef.current || !text) return;
      const pendingDraft =
        draftRef.current?.tempId === id ? draftRef.current : null;
      if (!pendingDraft && !threadsRef.current.some((t) => t.id === id)) return;

      const controller = new AbortController();
      abortRef.current = controller;
      let threadId = id;
      let userMessageId: string | null = null;
      let answer = "";
      let answerId = "";
      const begin: SideStreaming = {
        sideQuestionId: id,
        question: text,
        text: "",
      };
      streamingRef.current = begin;
      setStreaming(begin);
      setError(null);

      const fail = (detail: string) => {
        if (userMessageId !== null) {
          const sent = userMessageId;
          setThreads((current) =>
            pendingDraft
              ? current.filter((t) => t.id !== threadId)
              : current.map((t) =>
                  t.id === threadId
                    ? {
                        ...t,
                        messages: t.messages.filter((m) => m.id !== sent),
                      }
                    : t,
                ),
          );
        }
        if (pendingDraft) {
          setDraft((draftRef.current = pendingDraft));
          setOpen((current) => {
            const next = new Set(current);
            next.delete(threadId);
            for (const opened of openOnly(
              withDraft(threadsRef.current, pendingDraft),
              pendingDraft.tempId,
            )) {
              next.add(opened);
            }
            return next;
          });
        }
        setError({
          id: pendingDraft ? pendingDraft.tempId : id,
          detail,
          content: text,
        });
      };

      const events: AsyncGenerator<SideStreamEvent> = pendingDraft
        ? streamNewSideQuestion(
            sessionId ?? "",
            {
              ...pendingDraft.anchor,
              quote: pendingDraft.quote,
              occurrence: pendingDraft.occurrence,
              content: text,
            },
            controller.signal,
          )
        : streamSideFollowUp(id, text, controller.signal);

      let finished = false;
      try {
        for await (const event of events) {
          if (event.type === "started") {
            threadId = event.sideQuestionId;
            userMessageId = event.userMessageId;
            const userMessage = {
              id: event.userMessageId,
              role: "user" as const,
              content: text,
            };
            if (pendingDraft) {
              setThreads((current) => [
                ...current,
                {
                  ...draftAsThread(pendingDraft),
                  id: threadId,
                  messages: [userMessage],
                },
              ]);
              setDraft((draftRef.current = null));
              setOpen((current) => {
                const next = new Set(current);
                next.delete(pendingDraft.tempId);
                next.add(threadId);
                return next;
              });
            } else {
              setThreads((current) =>
                current.map((t) =>
                  t.id === threadId
                    ? { ...t, messages: [...t.messages, userMessage] }
                    : t,
                ),
              );
            }
            const started = {
              sideQuestionId: threadId,
              question: "",
              text: "",
            };
            streamingRef.current = started;
            setStreaming(started);
            answerId = event.answerMessageId;
          } else if (event.type === "chunk") {
            answer += event.content;
            const current = answer;
            setStreaming((s) => (s ? { ...s, text: current } : s));
          } else if (event.type === "end") {
            const final = answer;
            const finalId = answerId;
            setThreads((current) =>
              current.map((t) =>
                t.id === threadId
                  ? {
                      ...t,
                      messages: [
                        ...t.messages,
                        { id: finalId, role: "assistant", content: final },
                      ],
                    }
                  : t,
              ),
            );
            finished = true;
          } else {
            fail(event.detail || FAILED_DETAIL);
            finished = true;
          }
        }
        if (!finished && !controller.signal.aborted) fail(FAILED_DETAIL);
      } catch (e) {
        if (!controller.signal.aborted) {
          fail(e instanceof ApiError && e.detail ? e.detail : FAILED_DETAIL);
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        streamingRef.current = null;
        setStreaming(null);
      }
    },
    [sessionId],
  );

  return {
    threads,
    draft,
    open,
    streaming,
    error,
    startDraft,
    send,
    toggle,
    openThread,
    foldAll,
    removeByAnchorMessage,
  };
}
