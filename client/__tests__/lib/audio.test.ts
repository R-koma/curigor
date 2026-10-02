import { afterEach, describe, expect, it, vi } from "vitest";
import {
  appendTranscript,
  isRewrite,
  pickRecordingMimeType,
  recordingWarning,
  transcriptionErrorMessage,
} from "@/lib/audio";
import { TranscriptionError } from "@/lib/api";

describe("appendTranscript", () => {
  it("returns the transcript when the input is empty", () => {
    expect(appendTranscript("", "二分探索")).toBe("二分探索");
  });

  it("treats whitespace-only input as empty", () => {
    expect(appendTranscript("  \n", "二分探索")).toBe("二分探索");
  });

  it("appends on a new line after existing text", () => {
    expect(appendTranscript("前の説明 ", "続きの説明")).toBe(
      "前の説明\n続きの説明",
    );
  });
});

describe("pickRecordingMimeType", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("prefers webm with opus", () => {
    vi.stubGlobal("MediaRecorder", { isTypeSupported: () => true });
    expect(pickRecordingMimeType()).toBe("audio/webm;codecs=opus");
  });

  it("falls back to mp4 on Safari", () => {
    vi.stubGlobal("MediaRecorder", {
      isTypeSupported: (type: string) => type === "audio/mp4",
    });
    expect(pickRecordingMimeType()).toBe("audio/mp4");
  });

  it("returns null when nothing is supported", () => {
    vi.stubGlobal("MediaRecorder", { isTypeSupported: () => false });
    expect(pickRecordingMimeType()).toBeNull();
  });

  it("returns null without MediaRecorder", () => {
    vi.stubGlobal("MediaRecorder", undefined);
    expect(pickRecordingMimeType()).toBeNull();
  });
});

describe("recordingWarning", () => {
  it("says nothing for most of the recording", () => {
    expect(recordingWarning(0)).toBeNull();
    expect(recordingWarning(269)).toBeNull();
  });

  it("warns for the last 30 seconds", () => {
    expect(recordingWarning(270)).toBe("あと 30 秒で自動で確定します");
    expect(recordingWarning(299)).toBe("あと 1 秒で自動で確定します");
  });

  it("never shows a negative count", () => {
    expect(recordingWarning(301)).toBe("あと 0 秒で自動で確定します");
  });
});

describe("transcriptionErrorMessage", () => {
  it("explains the daily limit", () => {
    expect(transcriptionErrorMessage(new TranscriptionError(429))).toBe(
      "今日の音声入力の上限に達しました",
    );
  });

  it("explains an oversized recording", () => {
    expect(transcriptionErrorMessage(new TranscriptionError(413))).toBe(
      "録音が長すぎます",
    );
  });

  it("explains an unsupported format", () => {
    expect(transcriptionErrorMessage(new TranscriptionError(415))).toBe(
      "この形式の音声には対応していません",
    );
  });

  it("asks to retry otherwise", () => {
    expect(transcriptionErrorMessage(new TranscriptionError(502))).toBe(
      "文字起こしに失敗しました。再試行してください",
    );
    expect(transcriptionErrorMessage(new Error("network"))).toBe(
      "文字起こしに失敗しました。再試行してください",
    );
  });
});

describe("isRewrite", () => {
  const dictated = "二分探索は半分にしぼる手法です。";

  it("is false when text is added at the end", () => {
    expect(isRewrite(dictated, `${dictated}計算量は対数です。`)).toBe(false);
  });

  it("is false when a misheard word is corrected in the middle", () => {
    expect(isRewrite(dictated, "二分探索は半分に絞る手法です。")).toBe(false);
  });

  it("is false when nothing was there before", () => {
    expect(isRewrite("", dictated)).toBe(false);
  });

  it("is true when the text is cleared", () => {
    expect(isRewrite(dictated, "")).toBe(true);
  });

  it("is true when everything is typed over, even if the ending happens to match", () => {
    expect(isRewrite(dictated, "ハッシュ表は平均で一定時間です。")).toBe(true);
  });
});
