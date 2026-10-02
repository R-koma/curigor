import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useVoiceRecorder } from "@/hooks/use-voice-recorder";
import { transcribeAudio, TranscriptionError } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, transcribeAudio: vi.fn() };
});

const mockTranscribe = vi.mocked(transcribeAudio);

class FakeMediaRecorder {
  static supported = new Set(["audio/webm;codecs=opus"]);
  static isTypeSupported = (type: string) =>
    FakeMediaRecorder.supported.has(type);
  static instances: FakeMediaRecorder[] = [];
  static chunk: Blob = new Blob(["voice"], { type: "audio/webm;codecs=opus" });
  static asyncStop = false;

  state: RecordingState = "inactive";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;

  constructor(
    public stream: MediaStream,
    public options: MediaRecorderOptions,
  ) {
    FakeMediaRecorder.instances.push(this);
  }

  start() {
    this.state = "recording";
  }

  stop() {
    this.state = "inactive";
    if (!FakeMediaRecorder.asyncStop) this.finish();
  }

  finish() {
    this.ondataavailable?.({ data: FakeMediaRecorder.chunk });
    this.onstop?.();
  }
}

const trackStop = vi.fn();
const getUserMedia = vi.fn();

beforeEach(() => {
  FakeMediaRecorder.asyncStop = false;
  FakeMediaRecorder.supported = new Set(["audio/webm;codecs=opus"]);
  FakeMediaRecorder.instances = [];
  FakeMediaRecorder.chunk = new Blob(["voice"], {
    type: "audio/webm;codecs=opus",
  });
  vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
  trackStop.mockReset();
  getUserMedia.mockReset();
  getUserMedia.mockResolvedValue({ getTracks: () => [{ stop: trackStop }] });
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia },
    configurable: true,
  });
  mockTranscribe.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function setup(onTranscript = vi.fn()) {
  const hook = renderHook(() =>
    useVoiceRecorder({ sessionId: "session-1", onTranscript }),
  );
  return { ...hook, onTranscript };
}

describe("useVoiceRecorder", () => {
  it("transcribes the recording when stopped and hands the text over", async () => {
    mockTranscribe.mockResolvedValueOnce("二分探索は半分に絞る");
    const { result, onTranscript } = setup();

    await act(() => result.current.start());

    expect(result.current.status).toBe("recording");
    expect(FakeMediaRecorder.instances[0].options).toEqual({
      mimeType: "audio/webm;codecs=opus",
      audioBitsPerSecond: 64_000,
    });

    act(() => result.current.stop());

    await waitFor(() =>
      expect(onTranscript).toHaveBeenCalledWith("二分探索は半分に絞る"),
    );
    expect(mockTranscribe).toHaveBeenCalledWith("session-1", expect.any(Blob));
    expect(result.current.status).toBe("idle");
    expect(trackStop).toHaveBeenCalled();
  });

  it("stops and transcribes on its own after five minutes", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"] });
    mockTranscribe.mockResolvedValueOnce("長い説明");
    const { result, onTranscript } = setup();

    await act(() => result.current.start());
    act(() => {
      vi.advanceTimersByTime(299_000);
    });

    expect(result.current.elapsedSeconds).toBe(299);
    expect(FakeMediaRecorder.instances[0].state).toBe("recording");

    await act(async () => {
      vi.advanceTimersByTime(1_000);
    });

    expect(FakeMediaRecorder.instances[0].state).toBe("inactive");
    expect(onTranscript).toHaveBeenCalledWith("長い説明");
  });

  it("keeps the recording after a failure and retries with the same audio", async () => {
    mockTranscribe
      .mockRejectedValueOnce(new TranscriptionError(502))
      .mockResolvedValueOnce("再送できた");
    const { result, onTranscript } = setup();

    await act(() => result.current.start());
    act(() => result.current.stop());

    await waitFor(() =>
      expect(result.current.error).toBe(
        "文字起こしに失敗しました。再試行してください",
      ),
    );
    expect(result.current.canRetry).toBe(true);
    expect(onTranscript).not.toHaveBeenCalled();

    await act(() => result.current.retry());

    expect(mockTranscribe.mock.calls[1][1]).toBe(
      mockTranscribe.mock.calls[0][1],
    );
    expect(onTranscript).toHaveBeenCalledWith("再送できた");
    expect(result.current.canRetry).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("tells the user when the daily limit is reached", async () => {
    mockTranscribe.mockRejectedValueOnce(new TranscriptionError(429));
    const { result } = setup();

    await act(() => result.current.start());
    act(() => result.current.stop());

    await waitFor(() =>
      expect(result.current.error).toBe("今日の音声入力の上限に達しました"),
    );
  });

  it("reports silence instead of inserting nothing", async () => {
    mockTranscribe.mockResolvedValueOnce("");
    const { result, onTranscript } = setup();

    await act(() => result.current.start());
    act(() => result.current.stop());

    await waitFor(() =>
      expect(result.current.error).toBe("音声を聞き取れませんでした"),
    );
    expect(onTranscript).not.toHaveBeenCalled();
  });

  it("does not upload an empty recording", async () => {
    FakeMediaRecorder.chunk = new Blob([]);
    const { result } = setup();

    await act(() => result.current.start());
    act(() => result.current.stop());

    expect(result.current.error).toBe("録音が短すぎます");
    expect(result.current.status).toBe("idle");
    expect(mockTranscribe).not.toHaveBeenCalled();
  });

  it("reports a denied microphone permission", async () => {
    getUserMedia.mockRejectedValueOnce(
      new DOMException("denied", "NotAllowedError"),
    );
    const { result } = setup();

    await act(() => result.current.start());

    expect(result.current.error).toBe("マイクの使用が許可されていません");
    expect(result.current.status).toBe("idle");
    expect(FakeMediaRecorder.instances).toHaveLength(0);
  });

  it("reports an unsupported browser", async () => {
    FakeMediaRecorder.supported = new Set();
    const { result } = setup();

    await act(() => result.current.start());

    expect(result.current.error).toBe(
      "このブラウザは音声入力に対応していません",
    );
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  it("starts only one recording when the button is pressed twice quickly", async () => {
    const { result } = setup();

    await act(async () => {
      await Promise.all([result.current.start(), result.current.start()]);
    });

    expect(getUserMedia).toHaveBeenCalledTimes(1);
    expect(FakeMediaRecorder.instances).toHaveLength(1);
  });

  it("releases the microphone and uploads nothing when unmounted while recording", async () => {
    const { result, unmount, onTranscript } = setup();
    await act(() => result.current.start());

    unmount();
    act(() => FakeMediaRecorder.instances[0].stop());

    expect(trackStop).toHaveBeenCalled();
    expect(mockTranscribe).not.toHaveBeenCalled();
    expect(onTranscript).not.toHaveBeenCalled();
  });

  it("releases the microphone when unmounted while the permission prompt is open", async () => {
    let grantMicrophone: (stream: unknown) => void = () => {};
    getUserMedia.mockReturnValueOnce(
      new Promise((resolve) => {
        grantMicrophone = resolve;
      }),
    );
    const { result, unmount } = setup();

    let starting: Promise<void> = Promise.resolve();
    act(() => {
      starting = result.current.start();
    });
    unmount();
    await act(async () => {
      grantMicrophone({ getTracks: () => [{ stop: trackStop }] });
      await starting;
    });

    expect(trackStop).toHaveBeenCalled();
    expect(FakeMediaRecorder.instances).toHaveLength(0);
  });

  it("does not hand over a transcript that finishes after unmount", async () => {
    let finishTranscription: (text: string) => void = () => {};
    mockTranscribe.mockReturnValueOnce(
      new Promise((resolve) => {
        finishTranscription = resolve;
      }),
    );
    const { result, unmount, onTranscript } = setup();
    await act(() => result.current.start());
    act(() => result.current.stop());
    await waitFor(() => expect(result.current.status).toBe("transcribing"));

    unmount();
    await act(async () => {
      finishTranscription("別の入力欄に入ってはいけない");
    });

    expect(onTranscript).not.toHaveBeenCalled();
  });

  it("transcribes before a learning session exists", async () => {
    mockTranscribe.mockResolvedValueOnce("二分探索を学びたい");
    const onTranscript = vi.fn();
    const { result } = renderHook(() =>
      useVoiceRecorder({ sessionId: null, onTranscript }),
    );

    await act(() => result.current.start());
    act(() => result.current.stop());

    await waitFor(() =>
      expect(onTranscript).toHaveBeenCalledWith("二分探索を学びたい"),
    );
    expect(mockTranscribe).toHaveBeenCalledWith(null, expect.any(Blob));
  });

  it("discards the recording when cancelled", async () => {
    const { result, onTranscript } = setup();

    await act(() => result.current.start());
    act(() => result.current.cancel());

    expect(result.current.status).toBe("idle");
    expect(result.current.error).toBeNull();
    expect(result.current.canRetry).toBe(false);
    expect(trackStop).toHaveBeenCalled();
    expect(mockTranscribe).not.toHaveBeenCalled();
    expect(onTranscript).not.toHaveBeenCalled();
  });

  it("records normally again after a cancelled recording", async () => {
    mockTranscribe.mockResolvedValueOnce("言い直した説明");
    const { result, onTranscript } = setup();

    await act(() => result.current.start());
    act(() => result.current.cancel());
    await act(() => result.current.start());
    act(() => result.current.stop());

    await waitFor(() =>
      expect(onTranscript).toHaveBeenCalledWith("言い直した説明"),
    );
    expect(mockTranscribe).toHaveBeenCalledTimes(1);
  });

  it("ignores cancel when not recording", () => {
    const { result } = setup();

    act(() => result.current.cancel());

    expect(result.current.status).toBe("idle");
  });

  it("exposes the microphone stream only while recording", async () => {
    mockTranscribe.mockResolvedValueOnce("x");
    const { result } = setup();

    expect(result.current.stream).toBeNull();
    await act(() => result.current.start());
    expect(result.current.stream).toBe(FakeMediaRecorder.instances[0].stream);

    act(() => result.current.stop());

    expect(result.current.stream).toBeNull();
  });

  it("is starting while the permission prompt is open", async () => {
    let grant: (stream: unknown) => void = () => {};
    getUserMedia.mockReturnValueOnce(
      new Promise((resolve) => {
        grant = resolve;
      }),
    );
    const { result } = setup();

    let starting: Promise<void> = Promise.resolve();
    act(() => {
      starting = result.current.start();
    });
    expect(result.current.status).toBe("starting");

    await act(async () => {
      grant({ getTracks: () => [{ stop: trackStop }] });
      await starting;
    });

    expect(result.current.status).toBe("recording");
  });

  it("leaves the starting state when the permission is refused", async () => {
    getUserMedia.mockRejectedValueOnce(
      new DOMException("denied", "NotAllowedError"),
    );
    const { result } = setup();

    await act(() => result.current.start());

    expect(result.current.status).toBe("idle");
    expect(result.current.error).toBe("マイクの使用が許可されていません");
  });

  it("is stopping from the moment it is confirmed until the recorder has stopped", async () => {
    FakeMediaRecorder.asyncStop = true;
    mockTranscribe.mockResolvedValueOnce("確定した内容");
    const { result, onTranscript } = setup();
    await act(() => result.current.start());

    act(() => result.current.stop());
    expect(result.current.status).toBe("stopping");

    await act(async () => {
      FakeMediaRecorder.instances[0].finish();
    });

    await waitFor(() =>
      expect(onTranscript).toHaveBeenCalledWith("確定した内容"),
    );
  });

  it("ignores cancel once it is stopping", async () => {
    FakeMediaRecorder.asyncStop = true;
    mockTranscribe.mockResolvedValueOnce("確定済み");
    const { result, onTranscript } = setup();
    await act(() => result.current.start());
    act(() => result.current.stop());

    act(() => result.current.cancel());
    await act(async () => {
      FakeMediaRecorder.instances[0].finish();
    });

    await waitFor(() => expect(onTranscript).toHaveBeenCalledWith("確定済み"));
    expect(mockTranscribe).toHaveBeenCalledTimes(1);
  });

  it("goes back to idle after a cancelled recording has stopped", async () => {
    FakeMediaRecorder.asyncStop = true;
    const { result } = setup();
    await act(() => result.current.start());

    act(() => result.current.cancel());
    expect(result.current.status).toBe("stopping");
    await act(async () => {
      FakeMediaRecorder.instances[0].finish();
    });

    expect(result.current.status).toBe("idle");
    expect(mockTranscribe).not.toHaveBeenCalled();
  });
});
