import type { SideAnchor, SideQuestion } from "@/lib/side-questions";

export interface SideDraft {
  tempId: string;
  parentId: string | null;
  anchor: SideAnchor;
  quote: string;
  occurrence: number;
  depth: number;
}

type Node = Pick<SideQuestion, "id" | "parentId">;

export function draftAsThread(draft: SideDraft): SideQuestion {
  return {
    id: draft.tempId,
    parentId: draft.parentId,
    anchorMessageId: draft.anchor.anchorMessageId ?? null,
    anchorSideMessageId: draft.anchor.anchorSideMessageId ?? null,
    quote: draft.quote,
    occurrence: draft.occurrence,
    depth: draft.depth,
    messages: [],
  };
}

export function pathTo(threads: Node[], id: string): string[] {
  const byId = new Map(threads.map((t) => [t.id, t]));
  const path: string[] = [];
  let current: string | null = id;
  while (current !== null && !path.includes(current)) {
    path.push(current);
    current = byId.get(current)?.parentId ?? null;
  }
  return path;
}

export function openOnly(threads: Node[], id: string): Set<string> {
  return new Set(pathTo(threads, id));
}

export function descendantsOf(threads: Node[], id: string): Set<string> {
  const found = new Set<string>([id]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const t of threads) {
      if (t.parentId !== null && found.has(t.parentId) && !found.has(t.id)) {
        found.add(t.id);
        grew = true;
      }
    }
  }
  return found;
}

export function closeWithDescendants(
  threads: Node[],
  open: Set<string>,
  id: string,
): Set<string> {
  const closing = descendantsOf(threads, id);
  return new Set([...open].filter((o) => !closing.has(o)));
}

export function childrenOf(
  threads: SideQuestion[],
  parentId: string,
  answerMessageId?: string,
): SideQuestion[] {
  return threads.filter(
    (t) =>
      t.parentId === parentId &&
      (answerMessageId === undefined ||
        t.anchorSideMessageId === answerMessageId),
  );
}

export function topLevelInOrder(
  threads: SideQuestion[],
  messageOrder: string[],
  positionOf?: (thread: SideQuestion) => number | null,
): SideQuestion[] {
  const messageIndex = (t: SideQuestion) => {
    const index = t.anchorMessageId
      ? messageOrder.indexOf(t.anchorMessageId)
      : -1;
    return index === -1 ? Number.MAX_SAFE_INTEGER : index;
  };
  return threads
    .map((thread, created) => ({
      thread,
      created,
      message: messageIndex(thread),
      position: positionOf?.(thread) ?? null,
    }))
    .filter(({ thread }) => thread.parentId === null)
    .sort(
      (a, b) =>
        a.message - b.message ||
        (a.position !== null && b.position !== null
          ? a.position - b.position
          : 0) ||
        a.thread.occurrence - b.thread.occurrence ||
        a.created - b.created,
    )
    .map(({ thread }) => thread);
}
