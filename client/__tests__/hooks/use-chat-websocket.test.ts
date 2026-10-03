import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatWebSocket } from "@/hooks/use-chat-websocket";
import type { SpeechBus } from "@/lib/speech-bus";

class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
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
  vi.stubGlobal("WebSocket", FakeWebSocket);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ json: async () => ({ token: "tok" }) }),
  );
});

afterEach(() => vi.unstubAllGlobals());

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
        content: "目的を教えてください",
        card: { questions: [] },
      }),
    );

    expect(listener.onText.mock.calls.map((c) => c[1])).toEqual([
      "一言です",
      "目的を教えてください",
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
    expect(result.current.messages[1].speechKey).toBe("resumed-1");
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
});
