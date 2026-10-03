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

    expect(listener.onText).toHaveBeenCalledWith("半分に");
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

    expect(listener.onText.mock.calls.map((c) => c[0])).toEqual([
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
