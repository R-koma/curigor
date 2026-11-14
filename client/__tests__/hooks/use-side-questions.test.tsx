import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useSideQuestions } from "@/hooks/use-side-questions";
import { ApiError } from "@/lib/api";
import type { SideDraft } from "@/lib/side-question-tree";
import {
  fetchSideQuestions,
  streamNewSideQuestion,
  streamSideFollowUp,
  type SideQuestion,
  type SideStreamEvent,
} from "@/lib/side-questions";

vi.mock("@/lib/side-questions", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/side-questions")>()),
  fetchSideQuestions: vi.fn(),
  streamNewSideQuestion: vi.fn(),
  streamSideFollowUp: vi.fn(),
}));

const loaded: SideQuestion[] = [
  {
    id: "q1",
    parentId: null,
    anchorMessageId: "m1",
    anchorSideMessageId: null,
    quote: "索引",
    occurrence: 0,
    depth: 0,
    messages: [
      { id: "u1", role: "user", content: "索引とは？" },
      { id: "a1", role: "assistant", content: "行の位置を指す一覧" },
    ],
  },
  {
    id: "q2",
    parentId: "q1",
    anchorMessageId: null,
    anchorSideMessageId: "a1",
    quote: "目次",
    occurrence: 0,
    depth: 1,
    messages: [
      { id: "u2", role: "user", content: "目次とは？" },
      { id: "a2", role: "assistant", content: "一覧" },
    ],
  },
];

const draft: SideDraft = {
  tempId: "draft-1",
  parentId: null,
  anchor: { anchorMessageId: "m1" },
  quote: "B木",
  occurrence: 0,
  depth: 0,
};

async function* events(
  list: SideStreamEvent[],
  gate?: Promise<void>,
): AsyncGenerator<SideStreamEvent> {
  for (const [i, event] of list.entries()) {
    if (i === 1 && gate) await gate;
    yield event;
  }
}

async function* failing(error: unknown): AsyncGenerator<SideStreamEvent> {
  throw error;
}

beforeEach(() => {
  vi.mocked(fetchSideQuestions).mockReset().mockResolvedValue(loaded);
  vi.mocked(streamNewSideQuestion).mockReset();
  vi.mocked(streamSideFollowUp).mockReset();
});

async function setup() {
  const hook = renderHook(() => useSideQuestions("s1", true));
  await waitFor(() => expect(hook.result.current.threads).toHaveLength(2));
  return hook;
}

describe("useSideQuestions", () => {
  it("loads threads folded on session start", async () => {
    const hook = await setup();

    expect(fetchSideQuestions).toHaveBeenCalledWith("s1");
    expect(hook.result.current.open.size).toBe(0);
    expect(hook.result.current.draft).toBeNull();
  });

  it("does nothing while disabled", async () => {
    const hook = renderHook(() => useSideQuestions("s1", false));
    await act(async () => {});

    expect(fetchSideQuestions).not.toHaveBeenCalled();
    expect(hook.result.current.threads).toEqual([]);
  });

  it("opening a child keeps the parent open", async () => {
    const hook = await setup();

    act(() => hook.result.current.openThread("q2"));

    expect(hook.result.current.open).toEqual(new Set(["q2", "q1"]));
  });

  it("draft is dropped when another thread opens", async () => {
    const hook = await setup();
    act(() => hook.result.current.startDraft(draft));
    expect(hook.result.current.open).toEqual(new Set(["draft-1"]));

    act(() => hook.result.current.openThread("q1"));

    expect(hook.result.current.draft).toBeNull();
    expect(hook.result.current.open).toEqual(new Set(["q1"]));
  });

  it("draft is dropped when folded", async () => {
    const hook = await setup();
    act(() => hook.result.current.startDraft(draft));

    act(() => hook.result.current.toggle("draft-1"));

    expect(hook.result.current.draft).toBeNull();
  });

  it("send on draft replaces it with the real thread on started", async () => {
    vi.mocked(streamNewSideQuestion).mockReturnValue(
      events([
        {
          type: "started",
          sideQuestionId: "q9",
          userMessageId: "u9",
          answerMessageId: "a9",
        },
        { type: "chunk", content: "枝の" },
        { type: "chunk", content: "多い木" },
        { type: "end" },
      ]),
    );
    const hook = await setup();
    act(() => hook.result.current.startDraft(draft));

    await act(async () => {
      await hook.result.current.send("draft-1", "B木とは？");
    });

    expect(streamNewSideQuestion).toHaveBeenCalledWith(
      "s1",
      {
        anchorMessageId: "m1",
        quote: "B木",
        occurrence: 0,
        content: "B木とは？",
      },
      expect.any(AbortSignal),
    );
    const created = hook.result.current.threads.find((t) => t.id === "q9");
    expect(created?.messages).toEqual([
      { id: "u9", role: "user", content: "B木とは？" },
      { id: "a9", role: "assistant", content: "枝の多い木" },
    ]);
    expect(hook.result.current.draft).toBeNull();
    expect(hook.result.current.open).toEqual(new Set(["q9"]));
    expect(hook.result.current.streaming).toBeNull();
  });

  it("second send while streaming is ignored", async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    vi.mocked(streamSideFollowUp).mockReturnValue(
      events(
        [
          {
            type: "started",
            sideQuestionId: "q1",
            userMessageId: "u3",
            answerMessageId: "a3",
          },
          { type: "chunk", content: "続き" },
          { type: "end" },
        ],
        gate,
      ),
    );
    const hook = await setup();

    let first: Promise<void> = Promise.resolve();
    act(() => {
      first = hook.result.current.send("q1", "もう少し");
    });
    await waitFor(() =>
      expect(hook.result.current.streaming?.sideQuestionId).toBe("q1"),
    );
    await act(async () => {
      await hook.result.current.send("q2", "別の質問");
    });
    release();
    await act(async () => {
      await first;
    });

    expect(streamSideFollowUp).toHaveBeenCalledTimes(1);
    expect(hook.result.current.threads[0].messages.map((m) => m.id)).toEqual([
      "u1",
      "a1",
      "u3",
      "a3",
    ]);
  });

  it("error event restores content and removes the pending message", async () => {
    vi.mocked(streamSideFollowUp).mockReturnValue(
      events([
        {
          type: "started",
          sideQuestionId: "q1",
          userMessageId: "u3",
          answerMessageId: "a3",
        },
        { type: "error", code: "side_question_failed", detail: "失敗しました" },
      ]),
    );
    const hook = await setup();

    await act(async () => {
      await hook.result.current.send("q1", "もう少し");
    });

    expect(hook.result.current.threads[0].messages.map((m) => m.id)).toEqual([
      "u1",
      "a1",
    ]);
    expect(hook.result.current.error).toEqual({
      id: "q1",
      detail: "失敗しました",
      content: "もう少し",
    });
    expect(hook.result.current.streaming).toBeNull();
  });

  it("failed first send returns to draft", async () => {
    vi.mocked(streamNewSideQuestion).mockReturnValue(
      events([
        {
          type: "started",
          sideQuestionId: "q9",
          userMessageId: "u9",
          answerMessageId: "a9",
        },
        { type: "error", code: "side_question_failed", detail: "失敗" },
      ]),
    );
    const hook = await setup();
    act(() => hook.result.current.startDraft(draft));

    await act(async () => {
      await hook.result.current.send("draft-1", "B木とは？");
    });

    expect(hook.result.current.threads.map((t) => t.id)).toEqual(["q1", "q2"]);
    expect(hook.result.current.draft).toEqual(draft);
    expect(hook.result.current.open).toEqual(new Set(["draft-1"]));
    expect(hook.result.current.error).toMatchObject({
      id: "draft-1",
      content: "B木とは？",
    });
  });

  it("an HTTP error keeps the draft and shows its detail", async () => {
    vi.mocked(streamNewSideQuestion).mockReturnValue(
      failing(new ApiError(429, "daily_turn_limit_reached", "上限です")),
    );
    const hook = await setup();
    act(() => hook.result.current.startDraft(draft));

    await act(async () => {
      await hook.result.current.send("draft-1", "B木とは？");
    });

    expect(hook.result.current.draft).toEqual(draft);
    expect(hook.result.current.error).toEqual({
      id: "draft-1",
      detail: "上限です",
      content: "B木とは？",
    });
  });

  it("removes threads anchored to a cancelled reply with their children", async () => {
    const hook = await setup();
    act(() => hook.result.current.openThread("q2"));

    act(() => hook.result.current.removeByAnchorMessage("m1"));

    expect(hook.result.current.threads).toEqual([]);
    expect(hook.result.current.open.size).toBe(0);
  });
});
