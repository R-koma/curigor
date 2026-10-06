import { act, renderHook, waitFor } from "@testing-library/react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from "vitest";
import {
  AUTH_EXPIRED_MESSAGE,
  CONNECTION_LOST_MESSAGE,
  RECONNECT_FAILED_MESSAGE,
  useChatWebSocket,
} from "@/hooks/use-chat-websocket";
import { VOICE_INTAKE_CLOSING } from "@/lib/intake";
import type { SpeechBus } from "@/lib/speech-bus";

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

  open() {
    this.onopen?.();
  }

  drop() {
    this.readyState = 3;
    this.onclose?.();
  }

  emit(message: object) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }
}

beforeEach(() => {
  FakeWebSocket.instances = [];
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

async function startSession() {
  const hook = renderHook(() => useChatWebSocket());
  await act(async () => {
    hook.result.current.startLearning("二分探索");
  });
  await waitFor(() => expect(FakeWebSocket.instances[0]?.sent).toHaveLength(1));
  const ws = FakeWebSocket.instances[0];
  act(() =>
    ws.emit({
      type: "session_started",
      session_id: "s-1",
      session_type: "learning",
    }),
  );
  act(() => ws.emit({ type: "assistant_message", content: "どうぞ" }));
  return { ...hook, ws };
}

describe("useChatWebSocket stt fields", () => {
  it("sends the stt method and latency with an auto-sent voice message", async () => {
    const { result, ws } = await startSession();

    act(() => {
      result.current.sendMessage(
        "半分です",
        undefined,
        undefined,
        "半分です",
        true,
        { sttMethod: "segmented", sttLatencyMs: 820 },
      );
    });

    expect(JSON.parse(ws.sent[1])).toMatchObject({
      type: "user_message",
      auto_sent: true,
      stt_method: "segmented",
      stt_latency_ms: 820,
    });
  });

  it("sends the stt fields with start_learning", async () => {
    const hook = renderHook(() => useChatWebSocket());
    await act(async () => {
      hook.result.current.startLearning("二分探索", {
        raw_transcript: "二分探索",
        auto_sent: true,
        stt_method: "segmented",
        stt_latency_ms: 640,
      });
    });
    await waitFor(() =>
      expect(FakeWebSocket.instances[0]?.sent).toHaveLength(1),
    );

    expect(JSON.parse(FakeWebSocket.instances[0].sent[0])).toMatchObject({
      stt_method: "segmented",
      stt_latency_ms: 640,
    });
  });
});

describe("useChatWebSocket cancel", () => {
  it("keeps the raw transcript and the auto-send flag through a cancel", async () => {
    const { result, ws } = await startSession();

    act(() =>
      result.current.sendMessage(
        "半分に絞る",
        undefined,
        undefined,
        "はんぶんにしぼる",
        true,
      ),
    );
    expect(JSON.parse(ws.sent[1])).toMatchObject({
      type: "user_message",
      raw_transcript: "はんぶんにしぼる",
      auto_sent: true,
    });
    act(() => ws.emit({ type: "assistant_message", content: "次の質問です" }));
    act(() =>
      ws.emit({
        type: "cancel_last_message_success",
        cancelled_content: "半分に絞る",
      }),
    );

    expect(result.current.editingMessage).toBe("半分に絞る");
    expect(result.current.editingRawTranscript).toBe("はんぶんにしぼる");
    expect(result.current.editingAutoSent).toBe(true);

    act(() => result.current.clearEditingMessage());
    expect(result.current.editingRawTranscript).toBeNull();
    expect(result.current.editingAutoSent).toBe(false);
  });

  it("does not mark a cancelled hand-sent voice message as auto-sent", async () => {
    const { result, ws } = await startSession();

    act(() =>
      result.current.sendMessage(
        "半分に絞る",
        undefined,
        undefined,
        "はんぶんにしぼる",
      ),
    );
    expect(JSON.parse(ws.sent[1]).auto_sent).toBeUndefined();
    act(() => ws.emit({ type: "assistant_message", content: "次の質問です" }));
    act(() =>
      ws.emit({
        type: "cancel_last_message_success",
        cancelled_content: "半分に絞る",
      }),
    );

    expect(result.current.editingRawTranscript).toBe("はんぶんにしぼる");
    expect(result.current.editingAutoSent).toBe(false);
  });
});

describe("useChatWebSocket speech bus", () => {
  function listen(result: { current: { speechBus: SpeechBus } }) {
    const listener = { onText: vi.fn(), onEnd: vi.fn(), onAbort: vi.fn() };
    result.current.speechBus.subscribe(listener);
    return listener;
  }

  it("passes streamed text and the end of a response", async () => {
    const { result, ws } = await startSession();
    const listener = listen(result);

    act(() => ws.emit({ type: "assistant_message_chunk", content: "半分に" }));
    act(() => ws.emit({ type: "assistant_message_end" }));

    expect(listener.onText).toHaveBeenCalledWith(expect.any(String), "半分に");
    expect(listener.onEnd).toHaveBeenCalledTimes(1);
  });

  it("passes a non-streamed message and an intake card as text then end", async () => {
    const { result, ws } = await startSession();
    const listener = listen(result);

    act(() => ws.emit({ type: "assistant_message", content: "一言です" }));
    act(() =>
      ws.emit({
        type: "intake_question",
        content: "始める前に教えてください",
        card: {
          questions: [
            {
              key: "source",
              header: "教材",
              question: "何を使って学びますか？（複数選択可）",
              options: [],
              multi_select: true,
              preselected: [],
            },
          ],
        },
      }),
    );

    expect(listener.onText.mock.calls.map((c) => c[1])).toEqual([
      "一言です",
      "始める前に教えてください\n何を使って学びますか？\n" +
        VOICE_INTAKE_CLOSING,
    ]);
    expect(listener.onEnd).toHaveBeenCalledTimes(2);
  });

  it("ends the response when the server reports an error", async () => {
    const { result, ws } = await startSession();
    const listener = listen(result);

    act(() => ws.emit({ type: "error", detail: "boom" }));

    expect(listener.onEnd).toHaveBeenCalledTimes(1);
  });

  it("aborts when the socket closes", async () => {
    const { result, ws } = await startSession();
    const listener = listen(result);

    act(() => ws.onclose?.());

    expect(listener.onAbort).toHaveBeenCalledTimes(1);
  });

  it("aborts when the session is reset", async () => {
    const { result } = await startSession();
    const listener = listen(result);

    act(() => result.current.resetSession());

    expect(listener.onAbort).toHaveBeenCalledTimes(1);
  });
});

describe("useChatWebSocket speech keys", () => {
  function listenTo(result: { current: { speechBus: SpeechBus } }) {
    const l = { onText: vi.fn(), onEnd: vi.fn(), onAbort: vi.fn() };
    result.current.speechBus.subscribe(l);
    return l;
  }

  it("gives a streamed response one key on both the bus and the message", async () => {
    const { result, ws } = await startSession();
    const l = listenTo(result);
    act(() => {
      result.current.sendMessage("説明します");
    });

    act(() => ws.emit({ type: "assistant_message_chunk", content: "半分に" }));
    act(() => ws.emit({ type: "assistant_message_chunk", content: "絞る。" }));
    act(() => ws.emit({ type: "assistant_message_end" }));

    const keys = l.onText.mock.calls.map((c) => c[0]);
    expect(new Set(keys).size).toBe(1);
    const last = result.current.messages[result.current.messages.length - 1];
    expect(last).toMatchObject({ role: "assistant", content: "半分に絞る。" });
    expect(last.speechKey).toBe(keys[0]);
  });

  it("gives the next response a different key", async () => {
    const { result, ws } = await startSession();
    act(() => {
      result.current.sendMessage("一つ目");
    });
    act(() => ws.emit({ type: "assistant_message", content: "返答一" }));
    act(() => {
      result.current.sendMessage("二つ目");
    });
    act(() => ws.emit({ type: "assistant_message", content: "返答二" }));

    const keys = result.current.messages
      .filter((m) => m.role === "assistant")
      .map((m) => m.speechKey);
    expect(keys.every(Boolean)).toBe(true);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("keys an intake card message with the key it sends to the bus", async () => {
    const { result, ws } = await startSession();
    const l = listenTo(result);

    act(() =>
      ws.emit({
        type: "intake_question",
        content: "目的を教えてください",
        card: { questions: [] },
      }),
    );

    const last = result.current.messages[result.current.messages.length - 1];
    expect(last.speechKey).toBe(l.onText.mock.calls[0][0]);
  });

  it("keys resumed assistant messages by position", () => {
    const { result } = renderHook(() => useChatWebSocket());

    act(() =>
      result.current.resumeSession("s-1", [
        { role: "user", content: "質問" },
        { role: "assistant", content: "返答" },
      ]),
    );

    expect(result.current.messages[0].speechKey).toBeUndefined();
    expect(result.current.messages[1].speechKey).toBe("resumed-s-1-1");
  });

  it("keys the same position of different resumed sessions differently", () => {
    const { result } = renderHook(() => useChatWebSocket());
    const history = [
      { role: "user" as const, content: "質問" },
      { role: "assistant" as const, content: "返答" },
    ];

    act(() => result.current.resumeSession("s-1", history));
    const first = result.current.messages[1].speechKey;
    act(() => result.current.resumeSession("s-2", history));

    expect(result.current.messages[1].speechKey).not.toBe(first);
  });

  it("aborts speech when another session is resumed", () => {
    const { result } = renderHook(() => useChatWebSocket());
    const listener = { onText: vi.fn(), onEnd: vi.fn(), onAbort: vi.fn() };
    result.current.speechBus.subscribe(listener);

    act(() => result.current.resumeSession("s-2", []));

    expect(listener.onAbort).toHaveBeenCalledTimes(1);
  });
});

describe("useChatWebSocket sendMessage", () => {
  it("reports whether the message was sent", async () => {
    const idle = renderHook(() => useChatWebSocket());
    let sent = true;

    act(() => {
      sent = idle.result.current.sendMessage("届かない");
    });

    expect(sent).toBe(false);
    expect(idle.result.current.messages).toEqual([]);

    const { result } = await startSession();
    act(() => {
      sent = result.current.sendMessage("届く");
    });

    expect(sent).toBe(true);
  });

  it("marks a message sent from the intake card", async () => {
    const { result } = await startSession();

    act(() => {
      result.current.sendMessage("教材: 入門書", undefined, {
        purpose: "",
        source: ["入門書"],
        prior_knowledge: "",
      });
    });
    act(() => {
      result.current.sendMessage("ふつうの発言");
    });

    const users = result.current.messages.filter((m) => m.role === "user");
    expect(users.at(-2)?.intakeAnswered).toBe(true);
    expect(users.at(-1)?.intakeAnswered).toBeUndefined();
  });
});

describe("useChatWebSocket synthesis", () => {
  it("starts a synthesis and reports when its insights are saved", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => ({
        ok: true,
        status: 200,
        json: async () =>
          url.endsWith("/api/auth/token")
            ? { token: "tok" }
            : { status: "completed", session_type: "synthesis" },
      })),
    );
    const hook = renderHook(() => useChatWebSocket());
    await act(async () => {
      hook.result.current.startSynthesis("c1");
    });
    await waitFor(() =>
      expect(FakeWebSocket.instances[0]?.sent).toHaveLength(1),
    );
    const ws = FakeWebSocket.instances[0];
    expect(JSON.parse(ws.sent[0])).toEqual({
      type: "start_synthesis",
      collection_id: "c1",
    });

    act(() => ws.emit({ type: "session_ended", session_id: "s-1" }));

    await waitFor(() =>
      expect(hook.result.current.isSynthesisSaved).toBe(true),
    );
  });

  async function endSynthesis(noteStatus: object) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => ({
        ok: true,
        status: 200,
        json: async () =>
          url.endsWith("/api/auth/token") ? { token: "tok" } : noteStatus,
      })),
    );
    const hook = renderHook(() => useChatWebSocket());
    await act(async () => {
      hook.result.current.startSynthesis("c1");
    });
    await waitFor(() =>
      expect(FakeWebSocket.instances[0]?.sent).toHaveLength(1),
    );
    act(() =>
      FakeWebSocket.instances[0].emit({
        type: "session_ended",
        session_id: "s-1",
      }),
    );
    return hook;
  }

  it("reports an error and not a save when the poll fails", async () => {
    const hook = await endSynthesis({
      status: "failed",
      session_type: "synthesis",
    });

    await waitFor(() => expect(hook.result.current.error).not.toBeNull());
    expect(hook.result.current.isSynthesisSaved).toBe(false);
  });

  it("does not report a save for a non-synthesis session", async () => {
    const hook = await endSynthesis({
      status: "completed",
      session_type: "review",
    });

    await waitFor(() =>
      expect(vi.mocked(fetch).mock.calls.map(([url]) => String(url))).toEqual(
        expect.arrayContaining([expect.stringContaining("/note-status")]),
      ),
    );
    await act(async () => {});
    expect(hook.result.current.isSynthesisSaved).toBe(false);
  });

  it("clears a stale error when the session is ended", async () => {
    const hook = renderHook(() => useChatWebSocket());
    await act(async () => {
      hook.result.current.startSynthesis("c1");
    });
    await waitFor(() =>
      expect(FakeWebSocket.instances[0]?.sent).toHaveLength(1),
    );
    act(() =>
      FakeWebSocket.instances[0].emit({ type: "error", detail: "stale" }),
    );
    expect(hook.result.current.error).toBe("stale");

    act(() => hook.result.current.endSession());

    expect(hook.result.current.error).toBeNull();
  });
});

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function waitForSockets(count: number) {
  await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(count));
}

describe("useChatWebSocket reconnect", () => {
  it("reconnects and resumes the session after an unexpected close", async () => {
    const { result, ws } = await startSession();
    const before = result.current.messages;
    vi.useFakeTimers();

    act(() => ws.drop());

    expect(result.current.isConnected).toBe(false);
    expect(result.current.isReconnecting).toBe(true);

    await advance(1000);
    await waitForSockets(2);
    const next = FakeWebSocket.instances[1];
    act(() => next.open());

    expect(next.sent.map((s) => JSON.parse(s))).toEqual([
      { type: "authenticate", token: "tok" },
      { type: "resume_session", session_id: "s-1" },
    ]);

    act(() =>
      next.emit({
        type: "session_resumed",
        session_id: "s-1",
        session_type: "learning",
      }),
    );

    expect(result.current.isConnected).toBe(true);
    expect(result.current.isReconnecting).toBe(false);
    expect(result.current.messages).toEqual(before);

    let sent = false;
    act(() => {
      sent = result.current.sendMessage("再開後の発言");
    });
    expect(sent).toBe(true);
    expect(JSON.parse(next.sent[2])).toMatchObject({
      type: "user_message",
      content: "再開後の発言",
    });
  });

  it("starts counting attempts again after a successful resume", async () => {
    const { result, ws } = await startSession();
    vi.useFakeTimers();

    act(() => ws.drop());
    await advance(1000);
    await waitForSockets(2);
    const second = FakeWebSocket.instances[1];
    act(() => second.open());
    act(() =>
      second.emit({
        type: "session_resumed",
        session_id: "s-1",
        session_type: "learning",
      }),
    );

    act(() => second.drop());
    await advance(1000);
    await waitForSockets(3);
    expect(result.current.isReconnecting).toBe(true);
  });

  it("does not reconnect after the session ends", async () => {
    const { result, ws } = await startSession();
    vi.useFakeTimers();

    act(() => ws.emit({ type: "session_ended" }));
    act(() => ws.drop());
    await advance(60_000);

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(result.current.isReconnecting).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("reports a lost connection for a synthesis session instead of resuming it", async () => {
    const { result } = renderHook(() => useChatWebSocket());
    await act(async () => {
      result.current.startSynthesis("c-1");
    });
    await waitFor(() =>
      expect(FakeWebSocket.instances[0]?.sent).toHaveLength(1),
    );
    const ws = FakeWebSocket.instances[0];
    act(() =>
      ws.emit({
        type: "session_started",
        session_id: "s-9",
        session_type: "synthesis",
      }),
    );
    vi.useFakeTimers();

    act(() => ws.drop());
    await advance(60_000);

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(result.current.error).toBe(CONNECTION_LOST_MESSAGE);
  });

  it("reports a lost connection before the session has started", async () => {
    const { result } = renderHook(() => useChatWebSocket());
    await act(async () => {
      result.current.startLearning("二分探索");
    });
    await waitFor(() =>
      expect(FakeWebSocket.instances[0]?.sent).toHaveLength(1),
    );

    act(() => FakeWebSocket.instances[0].drop());

    expect(result.current.isReconnecting).toBe(false);
    expect(result.current.error).toBe(CONNECTION_LOST_MESSAGE);
  });

  it("stops a pending reconnect when the session is reset", async () => {
    const { result, ws } = await startSession();
    vi.useFakeTimers();

    act(() => ws.drop());
    act(() => result.current.resetSession());
    await advance(60_000);

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(result.current.isReconnecting).toBe(false);
  });

  it("gives up after the last attempt fails", async () => {
    const { result, ws } = await startSession();
    vi.useFakeTimers();

    act(() => ws.drop());
    for (let i = 1; i <= 5; i++) {
      await advance(30_000);
      await waitForSockets(i + 1);
      act(() => FakeWebSocket.instances[i].drop());
    }

    expect(result.current.isReconnecting).toBe(false);
    expect(result.current.error).toBe(RECONNECT_FAILED_MESSAGE);

    await advance(60_000);
    expect(FakeWebSocket.instances).toHaveLength(6);
  });

  it("stops when the server refuses to resume", async () => {
    const { result, ws } = await startSession();
    vi.useFakeTimers();

    act(() => ws.drop());
    await advance(1000);
    await waitForSockets(2);
    const next = FakeWebSocket.instances[1];
    act(() => next.open());
    act(() => next.emit({ type: "error", detail: "Session is not resumable" }));

    expect(result.current.isReconnecting).toBe(false);
    expect(result.current.error).toBe("Session is not resumable");

    act(() => next.drop());
    await advance(60_000);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("asks to sign in again when no token can be obtained", async () => {
    const { result, ws } = await startSession();
    vi.useFakeTimers();
    (fetch as Mock).mockResolvedValue({ json: async () => ({}) });

    act(() => ws.drop());
    await advance(1000);
    await vi.waitFor(() =>
      expect(result.current.error).toBe(AUTH_EXPIRED_MESSAGE),
    );

    expect(result.current.isReconnecting).toBe(false);
    await advance(60_000);
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("retries when the token request fails on the network", async () => {
    const { ws } = await startSession();
    vi.useFakeTimers();
    (fetch as Mock).mockRejectedValueOnce(new TypeError("Failed to fetch"));

    act(() => ws.drop());
    await advance(1000);
    expect(FakeWebSocket.instances).toHaveLength(1);

    await advance(2000);
    await waitForSockets(2);
  });

  it("lets the user type again when the connection drops mid-response", async () => {
    const { result, ws } = await startSession();
    act(() => result.current.sendMessage("半分に絞る"));
    act(() => ws.emit({ type: "assistant_message_chunk", content: "途中" }));
    expect(result.current.isLoading).toBe(true);
    vi.useFakeTimers();

    act(() => ws.drop());

    expect(result.current.isLoading).toBe(false);
  });

  it("reconnects at once when the network comes back", async () => {
    const { ws } = await startSession();
    vi.useFakeTimers();

    act(() => ws.drop());
    await act(async () => {
      window.dispatchEvent(new Event("online"));
      await vi.advanceTimersByTimeAsync(0);
    });
    await waitForSockets(2);

    await advance(1000);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("tries again when the tab becomes visible after giving up", async () => {
    const { result, ws } = await startSession();
    vi.useFakeTimers();

    act(() => ws.drop());
    for (let i = 1; i <= 5; i++) {
      await advance(30_000);
      await waitForSockets(i + 1);
      act(() => FakeWebSocket.instances[i].drop());
    }
    expect(result.current.isReconnecting).toBe(false);

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      await vi.advanceTimersByTimeAsync(0);
    });
    await waitForSockets(7);
    expect(result.current.isReconnecting).toBe(true);
  });

  it("does not reconnect while the tab is hidden", async () => {
    const { ws } = await startSession();
    vi.useFakeTimers();
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "hidden",
    });

    try {
      act(() => ws.drop());
      act(() => {
        document.dispatchEvent(new Event("visibilitychange"));
      });

      expect(FakeWebSocket.instances).toHaveLength(1);
    } finally {
      Reflect.deleteProperty(document, "visibilityState");
    }
  });

  async function dropAndResume(ws: FakeWebSocket, resumeFrames: object[] = []) {
    act(() => ws.drop());
    await advance(1000);
    await waitForSockets(2);
    const next = FakeWebSocket.instances[1];
    act(() => next.open());
    act(() =>
      next.emit({
        type: "session_resumed",
        session_id: "s-1",
        session_type: "learning",
      }),
    );
    resumeFrames.forEach((frame) => act(() => next.emit(frame)));
    return next;
  }

  it("returns a message that never reached the server to the input", async () => {
    const { result, ws } = await startSession();
    const before = result.current.messages;
    act(() => result.current.sendMessage("届かない発言"));
    vi.useFakeTimers();

    await dropAndResume(ws);

    expect(result.current.messages).toEqual(before);
    expect(result.current.editingMessage).toBe("届かない発言");
    expect(result.current.isLoading).toBe(false);
  });

  it("drops the partial reply when the server already rolled the turn back", async () => {
    const { result, ws } = await startSession();
    const before = result.current.messages;
    act(() => result.current.sendMessage("半分に絞る"));
    act(() => ws.emit({ type: "assistant_message_chunk", content: "途中" }));
    vi.useFakeTimers();

    await dropAndResume(ws);

    expect(result.current.messages).toEqual(before);
    expect(result.current.editingMessage).toBe("半分に絞る");
  });

  it("does not remove more messages when the server also reports the rollback", async () => {
    const { result, ws } = await startSession();
    const before = result.current.messages;
    act(() => result.current.sendMessage("半分に絞る"));
    vi.useFakeTimers();

    await dropAndResume(ws, [
      { type: "pending_message_rolled_back", content: "半分に絞る" },
    ]);

    expect(result.current.messages).toEqual(before);
    expect(result.current.editingMessage).toBe("半分に絞る");
  });

  it("leaves an answered turn alone when the connection drops afterwards", async () => {
    const { result, ws } = await startSession();
    act(() => result.current.sendMessage("半分に絞る"));
    act(() => ws.emit({ type: "assistant_message", content: "なるほど" }));
    const before = result.current.messages;
    vi.useFakeTimers();

    await dropAndResume(ws);

    expect(result.current.messages).toEqual(before);
    expect(result.current.editingMessage).toBeNull();
  });

  it("restores an empty draft for an unanswered intake card reply", async () => {
    const { result, ws } = await startSession();
    const before = result.current.messages;
    act(() =>
      result.current.sendMessage("整形済みの回答", undefined, {
        purpose: "試験対策",
        source: ["教科書"],
        prior_knowledge: "初心者",
      }),
    );
    vi.useFakeTimers();

    await dropAndResume(ws);

    expect(result.current.messages).toEqual(before);
    expect(result.current.editingMessage).toBe("");
  });

  it("does not send until the session has been resumed", async () => {
    const { result, ws } = await startSession();
    vi.useFakeTimers();

    act(() => ws.drop());
    await advance(1000);
    await waitForSockets(2);
    const next = FakeWebSocket.instances[1];
    act(() => next.open());

    let sent = true;
    act(() => {
      sent = result.current.sendMessage("再開前の発言");
    });
    expect(sent).toBe(false);

    act(() =>
      next.emit({
        type: "session_resumed",
        session_id: "s-1",
        session_type: "learning",
      }),
    );
    act(() => {
      sent = result.current.sendMessage("再開後の発言");
    });
    expect(sent).toBe(true);
  });

  it("ignores the late close of a socket that was already replaced", async () => {
    const { result, ws } = await startSession();
    vi.useFakeTimers();
    ws.readyState = 2;

    await act(async () => {
      window.dispatchEvent(new Event("online"));
      await vi.advanceTimersByTimeAsync(0);
    });
    await waitForSockets(2);
    const next = FakeWebSocket.instances[1];
    act(() => next.open());
    act(() =>
      next.emit({
        type: "session_resumed",
        session_id: "s-1",
        session_type: "learning",
      }),
    );

    act(() => ws.onclose?.());

    expect(result.current.isConnected).toBe(true);
  });

  it("does not reconnect after unmount", async () => {
    const { ws, unmount } = await startSession();
    vi.useFakeTimers();

    act(() => ws.drop());
    unmount();
    window.dispatchEvent(new Event("online"));
    await advance(60_000);

    expect(FakeWebSocket.instances).toHaveLength(1);
  });
});
