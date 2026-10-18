import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatWebSocket } from "@/hooks/use-chat-websocket";
import { fetchAPI } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  fetchAPI: vi.fn(),
  getToken: vi.fn(async () => "tok"),
}));

class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];
  readyState = 1;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = 3;
  }

  emit(message: object) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.mocked(fetchAPI).mockReset();
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function startExploreSession(
  options?: Parameters<ReturnType<typeof useChatWebSocket>["startExplore"]>[1],
) {
  const hook = renderHook(() => useChatWebSocket());
  await act(async () => {
    hook.result.current.startExplore("二分探索", options);
  });
  await waitFor(() => expect(FakeWebSocket.instances[0]?.sent).toHaveLength(1));
  const ws = FakeWebSocket.instances[0];
  act(() =>
    ws.emit({
      type: "session_started",
      session_id: "s1",
      session_type: "explore",
    }),
  );
  return { hook, ws };
}

describe("useChatWebSocket startExplore", () => {
  it("sends source with the start_explore payload", async () => {
    const source = { note_id: "n1", feedback_id: "f1", improvement_index: 2 };
    const { ws } = await startExploreSession({ source });

    expect(JSON.parse(ws.sent[0])).toEqual({
      type: "start_explore",
      topic: "二分探索",
      source,
    });
  });

  it("exposes the error code", async () => {
    const { hook, ws } = await startExploreSession();
    act(() =>
      ws.emit({
        type: "error",
        code: "improvement_not_found",
        detail: "この改善点は新しいフィードバックで置き換わりました",
      }),
    );
    expect(hook.result.current.errorCode).toBe("improvement_not_found");
  });

  it("sends start_explore with the topic and shows it as the first message", async () => {
    const { hook, ws } = await startExploreSession();

    expect(JSON.parse(ws.sent[0])).toEqual({
      type: "start_explore",
      topic: "二分探索",
    });
    expect(hook.result.current.messages[0]).toEqual({
      role: "user",
      content: "二分探索",
    });
    expect(hook.result.current.isLoading).toBe(true);
    expect(hook.result.current.sessionType).toBe("explore");
  });

  it("sends the voice fields only for an auto-sent voice start", async () => {
    const { ws } = await startExploreSession({
      raw_transcript: "にぶんたんさく",
      auto_sent: true,
      stt_method: "streaming",
      stt_latency_ms: 420,
    });

    expect(JSON.parse(ws.sent[0])).toEqual({
      type: "start_explore",
      topic: "二分探索",
      raw_transcript: "にぶんたんさく",
      auto_sent: true,
      stt_method: "streaming",
      stt_latency_ms: 420,
    });
  });
});

describe("useChatWebSocket explore session type", () => {
  it("takes the session type from session_started and restores it on resume", async () => {
    const { hook } = await startExploreSession();
    expect(hook.result.current.sessionType).toBe("explore");

    const resumed = renderHook(() => useChatWebSocket());
    await act(async () => {
      resumed.result.current.resumeSession("s9", [
        { role: "user", content: "二分探索" },
      ]);
    });
    await waitFor(() =>
      expect(FakeWebSocket.instances[1]?.sent).toHaveLength(1),
    );
    act(() =>
      FakeWebSocket.instances[1].emit({
        type: "session_resumed",
        session_id: "s9",
        session_type: "explore",
      }),
    );

    expect(resumed.result.current.sessionType).toBe("explore");
  });

  it("clears the session type and the memo on reset", async () => {
    const { hook } = await startExploreSession();

    act(() => hook.result.current.resetSession());

    expect(hook.result.current.sessionType).toBeNull();
    expect(hook.result.current.generatedStudyMemo).toBeNull();
  });
});

describe("useChatWebSocket explore end", () => {
  it("exposes the study memo once the note status reports it", async () => {
    vi.mocked(fetchAPI).mockResolvedValue({
      status: "completed",
      session_type: "explore",
      study_memo_id: "m1",
      topic: "二分探索",
    });
    const { hook, ws } = await startExploreSession();

    act(() => ws.emit({ type: "session_ended", session_id: "s1" }));

    await waitFor(() =>
      expect(hook.result.current.generatedStudyMemo).toEqual({
        id: "m1",
        topic: "二分探索",
      }),
    );
    expect(fetchAPI).toHaveBeenCalledWith(
      "/api/dialogue-sessions/s1/note-status",
    );
    expect(hook.result.current.isGeneratingNote).toBe(false);
    expect(hook.result.current.generatedNote).toBeNull();
  });

  it("does not poll when no memo was created", async () => {
    const { hook, ws } = await startExploreSession();

    act(() => ws.emit({ type: "session_ended", note_skipped: true }));

    expect(hook.result.current.noteSkipped).toBe(true);
    expect(hook.result.current.isGeneratingNote).toBe(false);
    expect(fetchAPI).not.toHaveBeenCalled();
  });

  it("words a failed memo creation with the study memo noun", async () => {
    vi.mocked(fetchAPI).mockResolvedValue({
      status: "failed",
      session_type: "explore",
    });
    const { hook, ws } = await startExploreSession();

    act(() => ws.emit({ type: "session_ended", session_id: "s1" }));

    await waitFor(() =>
      expect(hook.result.current.error).toBe(
        "学習メモを作成できませんでした。もう一度お試しください",
      ),
    );
    expect(hook.result.current.isGeneratingNote).toBe(false);
  });

  it("stops generating when completed carries no study memo id", async () => {
    vi.mocked(fetchAPI).mockResolvedValue({
      status: "completed",
      session_type: "explore",
    });
    const { hook, ws } = await startExploreSession();

    act(() => ws.emit({ type: "session_ended", session_id: "s1" }));

    await waitFor(() => expect(fetchAPI).toHaveBeenCalled());
    await waitFor(() =>
      expect(hook.result.current.isGeneratingNote).toBe(false),
    );
    expect(hook.result.current.generatedStudyMemo).toBeNull();
  });
});

describe("useChatWebSocket startLearning from a study memo", () => {
  async function startLearning(options?: { study_memo_id?: string }) {
    const hook = renderHook(() => useChatWebSocket());
    await act(async () => {
      hook.result.current.startLearning("二分探索", options);
    });
    await waitFor(() =>
      expect(FakeWebSocket.instances[0]?.sent).toHaveLength(1),
    );
    return JSON.parse(FakeWebSocket.instances[0].sent[0]);
  }

  it("sends the study memo id", async () => {
    expect(await startLearning({ study_memo_id: "m1" })).toEqual({
      type: "start_learning",
      topic: "二分探索",
      study_memo_id: "m1",
    });
  });

  it("sends none for an ordinary start", async () => {
    expect(await startLearning()).toEqual({
      type: "start_learning",
      topic: "二分探索",
    });
  });
});
