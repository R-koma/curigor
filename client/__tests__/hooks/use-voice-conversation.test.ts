import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import {
  MIC_DENIED_MESSAGE,
  TRANSCRIPTION_LIMIT_MESSAGE,
  useVoiceConversation,
  type VoiceUtterance,
} from "@/hooks/use-voice-conversation";
import { TranscriptionError } from "@/lib/api";
import type { OpenMic } from "@/lib/mic-capture";
import { DEFAULT_VAD_CONFIG, NOISE_CALIBRATION_MS } from "@/lib/vad";
import { FRAME_SAMPLES, type Samples } from "@/lib/pcm";
import { createSpeechBus } from "@/lib/speech-bus";

const speech = vi.hoisted(() => ({
  stop: vi.fn(),
  silence: vi.fn(),
  unlock: vi.fn(),
  playMessage: vi.fn(),
  activeKey: null as string | null,
  isSpeaking: false,
  error: null as string | null,
  enabledCalls: [] as boolean[],
}));

vi.mock("@/hooks/use-assistant-speech", () => ({
  useAssistantSpeech: (options: { enabled: boolean }) => {
    speech.enabledCalls.push(options.enabled);
    return speech;
  },
}));

const frameMs = DEFAULT_VAD_CONFIG.frameMs;
const loud = () => new Float32Array(FRAME_SAMPLES).fill(0.2);
const quiet = () => new Float32Array(FRAME_SAMPLES);

interface Harness {
  emit: (frame: Samples) => void;
  close: Mock<() => void>;
  results: {
    resolve: (text: string) => void;
    reject: (error: unknown) => void;
  }[];
  clock: { value: number };
  opens: number;
  openError: unknown;
}

function setup(
  overrides: {
    isResponding?: boolean;
    holdForReview?: boolean;
    onSend?: (u: VoiceUtterance) => boolean;
  } = {},
) {
  const harness: Harness = {
    emit: () => {},
    close: vi.fn<() => void>(),
    results: [],
    clock: { value: 0 },
    opens: 0,
    openError: null,
  };
  const onSend = vi.fn(overrides.onSend ?? (() => true));
  const onHold = vi.fn();
  const bus = createSpeechBus();
  const hook = renderHook(
    (props: { isResponding: boolean; holdForReview: boolean }) =>
      useVoiceConversation({
        sessionId: "s-1",
        bus,
        isResponding: props.isResponding,
        holdForReview: props.holdForReview,
        topic: "二分探索",
        onSend,
        onHold,
        openMic: async (onFrame) => {
          harness.opens += 1;
          if (harness.openError) throw harness.openError;
          harness.emit = onFrame;
          return { close: harness.close };
        },
        transcribe: () =>
          new Promise<string>((resolve, reject) =>
            harness.results.push({ resolve, reject }),
          ),
        now: () => harness.clock.value,
      }),
    {
      initialProps: {
        isResponding: overrides.isResponding ?? false,
        holdForReview: overrides.holdForReview ?? false,
      },
    },
  );
  return { ...hook, harness, onSend, onHold, bus };
}

function feed(harness: Harness, make: () => Samples, ms: number) {
  act(() => {
    for (let i = 0; i < ms / frameMs; i++) {
      harness.clock.value += frameMs;
      harness.emit(make());
    }
  });
}

async function started(
  harness: Harness,
  result: { current: { start: () => Promise<void> } },
) {
  await act(() => result.current.start());
  feed(harness, quiet, NOISE_CALIBRATION_MS);
}

async function speakSegment(harness: Harness, text: string) {
  feed(harness, loud, 400);
  feed(harness, quiet, 700);
  const result = harness.results.at(-1)!;
  await act(async () => result.resolve(text));
}

beforeEach(() => {
  [speech.stop, speech.silence, speech.unlock, speech.playMessage].forEach(
    (fn) => fn.mockReset(),
  );
  speech.isSpeaking = false;
  speech.enabledCalls = [];
});

function hide(hidden: boolean) {
  Object.defineProperty(document, "hidden", {
    configurable: true,
    value: hidden,
  });
  act(() => document.dispatchEvent(new Event("visibilitychange")));
}

describe("useVoiceConversation", () => {
  it("unlocks audio and listens after start", async () => {
    const { result, harness } = setup();
    await started(harness, result);
    expect(speech.unlock).toHaveBeenCalled();
    expect(result.current.status).toBe("listening");
  });

  it("sends the joined transcript without the closing word", async () => {
    const { result, harness, onSend } = setup();
    await started(harness, result);
    await speakSegment(harness, "二分探索は");
    await speakSegment(harness, "半分に絞ります。以上");

    expect(onSend).toHaveBeenCalledTimes(1);
    const utterance = onSend.mock.calls[0][0];
    expect(utterance).toMatchObject({
      content: "二分探索は半分に絞ります",
      rawTranscript: "二分探索は半分に絞ります",
      sttMethod: "segmented",
    });
    expect(utterance.sttLatencyMs).toBe(0);
    expect(result.current.segments).toEqual([]);
  });

  it("does not send without the closing word", async () => {
    const { result, harness, onSend } = setup();
    await started(harness, result);
    await speakSegment(harness, "考え中です");
    expect(onSend).not.toHaveBeenCalled();
    expect(result.current.segments.map((s) => s.text)).toEqual(["考え中です"]);
  });

  it("does not send while the user is speaking again", async () => {
    const { result, harness, onSend } = setup();
    await started(harness, result);
    feed(harness, loud, 400);
    feed(harness, quiet, 700);
    feed(harness, loud, 400);
    await act(async () => harness.results[0].resolve("以上"));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("defers the send until the response finishes", async () => {
    const { result, harness, onSend, rerender } = setup({ isResponding: true });
    await started(harness, result);
    await speakSegment(harness, "次の質問です。以上");
    expect(onSend).not.toHaveBeenCalled();

    rerender({ isResponding: false, holdForReview: false });
    await act(async () => {});
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("silences the assistant when the user starts speaking", async () => {
    const { result, harness } = setup();
    await started(harness, result);
    speech.isSpeaking = true;
    feed(harness, loud, 300);
    expect(speech.silence).toHaveBeenCalledWith(false);
  });

  it("also skips the upcoming response when speaking while thinking", async () => {
    const { result, harness } = setup({ isResponding: true });
    await started(harness, result);
    feed(harness, loud, 200);
    expect(speech.silence).toHaveBeenCalledWith(true);
  });

  it("hands the utterance over for review while the intake card is shown", async () => {
    const { result, harness, onSend, onHold } = setup({ holdForReview: true });
    await started(harness, result);
    await speakSegment(harness, "仕事で使うためです。以上");

    expect(onSend).not.toHaveBeenCalled();
    expect(onHold.mock.calls[0][0].content).toBe("仕事で使うためです");
    expect(result.current.status).toBe("off");
    expect(harness.close).toHaveBeenCalled();
  });

  it("sendNow skips failed segments and needs no closing word", async () => {
    const { result, harness, onSend } = setup();
    await started(harness, result);
    feed(harness, loud, 400);
    feed(harness, quiet, 700);
    await act(async () => harness.results[0].reject(new Error("boom")));
    await speakSegment(harness, "半分に絞る");

    await act(() => result.current.sendNow());
    expect(onSend.mock.calls[0][0].content).toBe("半分に絞る");
  });

  it("keeps the segments and reports when sending fails", async () => {
    const { result, harness } = setup({ onSend: () => false });
    await started(harness, result);
    await speakSegment(harness, "半分です。以上");
    expect(result.current.segments).toHaveLength(1);
    expect(result.current.error).not.toBeNull();
  });

  it("closes the panel on the daily transcription limit", async () => {
    const { result, harness } = setup();
    await started(harness, result);
    feed(harness, loud, 400);
    feed(harness, quiet, 700);
    await act(async () =>
      harness.results[0].reject(new TranscriptionError(429)),
    );
    expect(result.current.status).toBe("off");
    expect(result.current.error).toBe(TRANSCRIPTION_LIMIT_MESSAGE);
  });

  it("pauses when the tab is hidden, releases the mic and ignores frames", async () => {
    const { result, harness } = setup();
    await started(harness, result);
    hide(true);
    expect(result.current.status).toBe("paused");
    expect(harness.close).toHaveBeenCalledTimes(1);
    feed(harness, loud, 400);
    feed(harness, quiet, 700);
    expect(harness.results).toHaveLength(0);
    hide(false);
  });

  it("pause closes the capture", async () => {
    const { result, harness } = setup();
    await started(harness, result);
    act(() => result.current.pause());
    expect(harness.close).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe("paused");
  });

  it("resume reopens the mic and listens after calibration", async () => {
    const { result, harness } = setup();
    await started(harness, result);
    act(() => result.current.pause());
    await act(() => result.current.resume());
    expect(harness.opens).toBe(2);
    feed(harness, quiet, NOISE_CALIBRATION_MS);
    expect(result.current.status).toBe("listening");
  });

  it("resume ignores a second call while reopening", async () => {
    const { result, harness } = setup();
    await started(harness, result);
    act(() => result.current.pause());
    await act(async () => {
      void result.current.resume();
      void result.current.resume();
    });
    expect(harness.opens).toBe(2);
  });

  it("resume stays paused while the tab is hidden", async () => {
    const { result, harness } = setup();
    await started(harness, result);
    hide(true);
    await act(() => result.current.resume());
    expect(harness.opens).toBe(1);
    expect(result.current.status).toBe("paused");
    hide(false);
  });

  it("resume ends the conversation with an error when the mic cannot reopen", async () => {
    const { result, harness } = setup();
    await started(harness, result);
    act(() => result.current.pause());
    harness.openError = new DOMException("denied", "NotAllowedError");
    await act(() => result.current.resume());
    expect(result.current.status).toBe("off");
    expect(result.current.error).toBe(MIC_DENIED_MESSAGE);
  });

  it("closes the capture that arrives after stop during a pending resume", async () => {
    const closes: ReturnType<typeof vi.fn>[] = [];
    const pending: (() => void)[] = [];
    const { result } = renderHook(() =>
      useVoiceConversation({
        sessionId: "s-1",
        bus: createSpeechBus(),
        isResponding: false,
        holdForReview: false,
        topic: null,
        onSend: () => true,
        onHold: () => {},
        openMic: () =>
          new Promise((resolve) => {
            const close = vi.fn();
            closes.push(close);
            pending.push(() => resolve({ close }));
          }),
      }),
    );
    let first: Promise<void>;
    act(() => {
      first = result.current.start();
    });
    await act(async () => {
      pending[0]();
      await first;
    });
    act(() => result.current.pause());
    let second: Promise<void>;
    act(() => {
      second = result.current.resume();
    });
    act(() => result.current.stop());
    await act(async () => {
      pending[1]();
      await second;
    });
    expect(closes[1]).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe("off");
  });

  it("pause while starting cancels the open and closes the late capture", async () => {
    const close = vi.fn();
    let resolveOpen: () => void = () => {};
    const { result } = renderHook(() =>
      useVoiceConversation({
        sessionId: "s-1",
        bus: createSpeechBus(),
        isResponding: false,
        holdForReview: false,
        topic: null,
        onSend: () => true,
        onHold: () => {},
        openMic: () =>
          new Promise((resolve) => {
            resolveOpen = () => resolve({ close });
          }),
      }),
    );
    let pending: Promise<void>;
    act(() => {
      pending = result.current.start();
    });
    act(() => result.current.pause());
    await act(async () => {
      resolveOpen();
      await pending;
    });
    expect(close).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe("paused");
  });

  it("ends an utterance in progress on pause without sending it", async () => {
    const { result, harness, onSend } = setup();
    await started(harness, result);
    feed(harness, loud, 400);
    act(() => result.current.pause());
    await act(async () => harness.results[0].resolve("途中です。以上"));
    expect(onSend).not.toHaveBeenCalled();
    expect(result.current.segments.map((s) => s.text)).toEqual([
      "途中です。以上",
    ]);
  });

  it("speaks responses only while active or starting, not while paused", async () => {
    const { result, harness } = setup();
    await started(harness, result);
    expect(speech.enabledCalls.at(-1)).toBe(true);
    act(() => result.current.pause());
    expect(speech.enabledCalls.at(-1)).toBe(false);
    await act(() => result.current.resume());
    expect(speech.enabledCalls.at(-1)).toBe(true);
  });

  it("measures the latency of Enter from the key press after a long idle", async () => {
    const { result, harness, onSend } = setup();
    await started(harness, result);
    await speakSegment(harness, "半分に絞る");
    harness.clock.value += 11 * 60_000;
    await act(() => result.current.sendNow());
    const latency = onSend.mock.calls[0][0].sttLatencyMs;
    expect(latency).toBeGreaterThanOrEqual(0);
    expect(latency).toBeLessThan(100);
  });

  it("clamps a stale turn end when a failed send is retried much later", async () => {
    let calls = 0;
    const { result, harness, onSend, rerender } = setup({
      onSend: () => ++calls > 1,
    });
    await started(harness, result);
    await speakSegment(harness, "半分です。以上");
    expect(onSend).toHaveBeenCalledTimes(1);
    harness.clock.value += 20 * 60_000;
    rerender({ isResponding: true, holdForReview: false });
    rerender({ isResponding: false, holdForReview: false });
    await act(async () => {});
    expect(onSend).toHaveBeenCalledTimes(2);
    expect(onSend.mock.calls[1][0].sttLatencyMs).toBe(600_000);
  });

  it("reports a denied microphone and stays off", async () => {
    const { result } = renderHook(() =>
      useVoiceConversation({
        sessionId: "s-1",
        bus: createSpeechBus(),
        isResponding: false,
        holdForReview: false,
        topic: null,
        onSend: () => true,
        onHold: () => {},
        openMic: async () => {
          throw new DOMException("denied", "NotAllowedError");
        },
      }),
    );
    await act(() => result.current.start());
    expect(result.current.status).toBe("off");
    expect(result.current.error).toBe(MIC_DENIED_MESSAGE);
  });

  it("records the first token after a send", async () => {
    const { result, harness, bus } = setup();
    await started(harness, result);
    await speakSegment(harness, "半分です。以上");
    harness.clock.value += 500;
    act(() => bus.text("r1", "はい"));
    expect(result.current.timings?.firstToken).toBe(
      result.current.timings!.sent + 500,
    );
  });

  it("stop closes the mic and the speech", async () => {
    const { result, harness } = setup();
    await started(harness, result);
    act(() => result.current.stop());
    expect(harness.close).toHaveBeenCalled();
    expect(speech.stop).toHaveBeenCalled();
    expect(result.current.status).toBe("off");
  });

  it("re-evaluates when a forced split segment resolves after the final one", async () => {
    const { result, harness, onSend } = setup();
    await started(harness, result);
    feed(harness, loud, 31_000);
    feed(harness, loud, 400);
    feed(harness, quiet, 700);
    expect(harness.results.length).toBeGreaterThanOrEqual(2);
    const last = harness.results.length - 1;
    await act(async () => harness.results[last].resolve("以上"));
    expect(onSend).not.toHaveBeenCalled();
    for (let i = 0; i < last; i++) {
      await act(async () => harness.results[i].resolve("長い話です。"));
    }
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("opens only one capture on a double start", async () => {
    const closes: ReturnType<typeof vi.fn>[] = [];
    const resolvers: (() => void)[] = [];
    const { result } = renderHook(() =>
      useVoiceConversation({
        sessionId: "s-1",
        bus: createSpeechBus(),
        isResponding: false,
        holdForReview: false,
        topic: null,
        onSend: () => true,
        onHold: () => {},
        openMic: () =>
          new Promise((resolve) => {
            const close = vi.fn();
            closes.push(close);
            resolvers.push(() => resolve({ close }));
          }),
      }),
    );
    let first: Promise<void>;
    let second: Promise<void>;
    act(() => {
      first = result.current.start();
      second = result.current.start();
    });
    expect(closes).toHaveLength(1);
    await act(async () => {
      resolvers[0]();
      await first;
      await second;
    });
    expect(closes[0]).not.toHaveBeenCalled();
    expect(result.current.status).toBe("listening");
  });

  function deferredMic() {
    const state = { close: vi.fn(), resolve: () => {} };
    const openMic: OpenMic = () =>
      new Promise((resolve) => {
        state.resolve = () => resolve({ close: state.close });
      });
    return { state, openMic };
  }

  it("closes the capture when stop is called while starting", async () => {
    const { state, openMic } = deferredMic();
    const { result } = renderHook(() =>
      useVoiceConversation({
        sessionId: "s-1",
        bus: createSpeechBus(),
        isResponding: false,
        holdForReview: false,
        topic: null,
        onSend: () => true,
        onHold: () => {},
        openMic,
      }),
    );
    let pending: Promise<void>;
    act(() => {
      pending = result.current.start();
    });
    act(() => result.current.stop());
    await act(async () => {
      state.resolve();
      await pending;
    });
    expect(state.close).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe("off");
  });

  it("closes the capture when unmounted while starting", async () => {
    const { state, openMic } = deferredMic();
    const { result, unmount } = renderHook(() =>
      useVoiceConversation({
        sessionId: "s-1",
        bus: createSpeechBus(),
        isResponding: false,
        holdForReview: false,
        topic: null,
        onSend: () => true,
        onHold: () => {},
        openMic,
      }),
    );
    let pending: Promise<void>;
    act(() => {
      pending = result.current.start();
    });
    unmount();
    await act(async () => {
      state.resolve();
      await pending;
    });
    expect(state.close).toHaveBeenCalledTimes(1);
  });

  it("defers sendNow until the response finishes", async () => {
    const { result, harness, onSend, rerender } = setup({ isResponding: true });
    await started(harness, result);
    await speakSegment(harness, "半分に絞る");
    await act(() => result.current.sendNow());
    expect(onSend).not.toHaveBeenCalled();

    rerender({ isResponding: false, holdForReview: false });
    await act(async () => {});
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend.mock.calls[0][0].content).toBe("半分に絞る");
  });

  it("clears the deferred send when only failed segments exist", async () => {
    const { result, harness, onSend, rerender } = setup({ isResponding: true });
    await started(harness, result);
    feed(harness, loud, 400);
    feed(harness, quiet, 700);
    await act(async () => harness.results[0].reject(new Error("boom")));
    await act(() => result.current.sendNow());
    rerender({ isResponding: false, holdForReview: false });
    await act(async () => {});
    expect(onSend).not.toHaveBeenCalled();

    await speakSegment(harness, "続きです");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not send a late transcription after unmount", async () => {
    const { result, harness, onSend, unmount } = setup();
    await started(harness, result);
    feed(harness, loud, 400);
    feed(harness, quiet, 700);
    unmount();
    await act(async () => harness.results[0].resolve("半分です。以上"));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("keeps a pending segment when the response ends after Enter", async () => {
    const { result, harness, onSend, rerender } = setup({ isResponding: true });
    await started(harness, result);
    await speakSegment(harness, "前半です");
    feed(harness, loud, 400);
    act(() => {
      void result.current.sendNow();
    });
    feed(harness, quiet, 700);
    rerender({ isResponding: false, holdForReview: false });
    await act(async () => {});
    expect(onSend).not.toHaveBeenCalled();

    await act(async () => harness.results.at(-1)!.resolve("後半です"));
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend.mock.calls[0][0].content).toBe("前半です後半です");
  });

  it("clears the forced send when sending fails", async () => {
    const { result, harness, onSend, rerender } = setup({
      isResponding: true,
      onSend: () => false,
    });
    await started(harness, result);
    await speakSegment(harness, "半分です");
    await act(() => result.current.sendNow());
    rerender({ isResponding: false, holdForReview: false });
    await act(async () => {});
    expect(onSend).toHaveBeenCalledTimes(1);

    await speakSegment(harness, "続きです");
    expect(onSend).toHaveBeenCalledTimes(1);
  });
});
