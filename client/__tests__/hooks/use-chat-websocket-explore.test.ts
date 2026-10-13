import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatWebSocket } from "@/hooks/use-chat-websocket";
import { fetchAPI } from "@/lib/api";

vi.mock("@/lib/api", () => ({ fetchAPI: vi.fn() }));

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

const OVERVIEW = {
  aspects: [
    {
      aspect_id: "a1",
      name: "真ん中との比較",
      summary: "真ん中と比べて半分を捨てる",
      is_core: true,
      explained: false,
    },
  ],
};

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.mocked(fetchAPI).mockReset();
  vi.stubGlobal("WebSocket", FakeWebSocket);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ json: async () => ({ token: "tok" }) }),
  );
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

describe("useChatWebSocket explore overview", () => {
  it("keeps the overview from the end of a response, and keeps it when a later end carries null", async () => {
    const { hook, ws } = await startExploreSession();
    expect(hook.result.current.exploreOverview).toBeNull();

    act(() =>
      ws.emit({ type: "assistant_message_end", explore_overview: OVERVIEW }),
    );
    expect(hook.result.current.exploreOverview).toEqual(OVERVIEW);

    act(() =>
      ws.emit({ type: "assistant_message_end", explore_overview: null }),
    );
    expect(hook.result.current.exploreOverview).toEqual(OVERVIEW);
  });

  it("ignores a malformed overview", async () => {
    const { hook, ws } = await startExploreSession();

    act(() =>
      ws.emit({ type: "assistant_message_end", explore_overview: "x" }),
    );

    expect(hook.result.current.exploreOverview).toBeNull();
  });

  it("restores the overview and the session type on resume", async () => {
    const hook = renderHook(() => useChatWebSocket());
    await act(async () => {
      hook.result.current.resumeSession("s9", [
        { role: "user", content: "二分探索" },
      ]);
    });
    await waitFor(() =>
      expect(FakeWebSocket.instances[0]?.sent).toHaveLength(1),
    );

    act(() =>
      FakeWebSocket.instances[0].emit({
        type: "session_resumed",
        session_id: "s9",
        session_type: "explore",
        explore_overview: OVERVIEW,
      }),
    );

    expect(hook.result.current.sessionType).toBe("explore");
    expect(hook.result.current.exploreOverview).toEqual(OVERVIEW);
  });

  it("clears the overview, the session type and the memo on reset", async () => {
    const { hook, ws } = await startExploreSession();
    act(() =>
      ws.emit({ type: "assistant_message_end", explore_overview: OVERVIEW }),
    );

    act(() => hook.result.current.resetSession());

    expect(hook.result.current.exploreOverview).toBeNull();
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
});
