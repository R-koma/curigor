import { beforeEach, describe, it, expect, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { ChatInput } from "@/components/chat/chat-input";
import type { VoiceRecorder } from "@/hooks/use-voice-recorder";

const mocks = vi.hoisted(() => ({
  voice: null as unknown as VoiceRecorder,
  onTranscript: null as ((text: string) => void) | null,
}));

vi.mock("@/hooks/use-voice-recorder", () => ({
  useVoiceRecorder: (options: { onTranscript: (text: string) => void }) => {
    mocks.onTranscript = options.onTranscript;
    return mocks.voice;
  },
}));

beforeEach(() => {
  mocks.voice = {
    status: "idle",
    elapsedSeconds: 0,
    error: null,
    canRetry: false,
    start: vi.fn(),
    stop: vi.fn(),
    retry: vi.fn(),
  };
  mocks.onTranscript = null;
});

function Harness({
  onSend,
  sessionId = "session-1",
  allowVoice = true,
}: {
  onSend: (content: string, images?: unknown, rawTranscript?: string) => void;
  sessionId?: string | null;
  allowVoice?: boolean;
}) {
  const [value, setValue] = useState("");
  return (
    <ChatInput
      value={value}
      onChange={setValue}
      onSend={onSend}
      isLoading={false}
      sessionId={sessionId}
      allowVoice={allowVoice}
    />
  );
}

function ReplaceableHarness({
  onSend,
}: {
  onSend: (content: string, images?: unknown, rawTranscript?: string) => void;
}) {
  const [value, setValue] = useState("");
  return (
    <>
      <button type="button" onClick={() => setValue("以前の発言を直したい")}>
        外から差し替え
      </button>
      <ChatInput
        value={value}
        onChange={setValue}
        onSend={onSend}
        isLoading={false}
        sessionId="session-1"
        allowVoice
      />
    </>
  );
}

describe("ChatInput", () => {
  it("offers image attachment by default", () => {
    const { container } = render(
      <ChatInput
        value=""
        onChange={vi.fn()}
        onSend={vi.fn()}
        isLoading={false}
      />,
    );

    expect(container.querySelector('input[type="file"]')).not.toBeNull();
  });

  it("hides image attachment when allowImages is false", () => {
    const { container } = render(
      <ChatInput
        value=""
        onChange={vi.fn()}
        onSend={vi.fn()}
        isLoading={false}
        allowImages={false}
      />,
    );

    expect(container.querySelector('input[type="file"]')).toBeNull();
  });

  it("hides the microphone unless voice is allowed", () => {
    render(
      <ChatInput
        value=""
        onChange={vi.fn()}
        onSend={vi.fn()}
        isLoading={false}
        sessionId="session-1"
      />,
    );

    expect(screen.queryByRole("button", { name: "音声で入力" })).toBeNull();
  });

  it("offers the microphone before a session exists when voice is allowed", async () => {
    const onSend = vi.fn();
    render(<Harness onSend={onSend} sessionId={null} />);

    await userEvent.click(screen.getByRole("button", { name: "音声で入力" }));
    expect(mocks.voice.start).toHaveBeenCalled();

    act(() => mocks.onTranscript!("二分探索を学びたい"));
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSend).toHaveBeenCalledWith(
      "二分探索を学びたい",
      undefined,
      "二分探索を学びたい",
    );
  });

  it("starts recording from the microphone button", async () => {
    render(<Harness onSend={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "音声で入力" }));

    expect(mocks.voice.start).toHaveBeenCalled();
  });

  it("sends the edited text together with the raw transcript", async () => {
    const onSend = vi.fn();
    render(<Harness onSend={onSend} />);

    act(() => mocks.onTranscript!("二分探索は半分にしぼる"));
    const textarea = screen.getByRole("textbox");
    expect(textarea).toHaveValue("二分探索は半分にしぼる");

    await userEvent.type(textarea, "手法");
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSend).toHaveBeenCalledWith(
      "二分探索は半分にしぼる手法",
      undefined,
      "二分探索は半分にしぼる",
    );
  });

  it("joins several transcripts into one raw transcript", async () => {
    const onSend = vi.fn();
    render(<Harness onSend={onSend} />);

    act(() => mocks.onTranscript!("前半"));
    act(() => mocks.onTranscript!("後半"));
    expect(screen.getByRole("textbox")).toHaveValue("前半\n後半");

    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSend).toHaveBeenCalledWith("前半\n後半", undefined, "前半\n後半");
  });

  it("does not attach a transcript the user cleared away", async () => {
    const onSend = vi.fn();
    render(<Harness onSend={onSend} />);

    act(() => mocks.onTranscript!("誤認識した文"));
    const textarea = screen.getByRole("textbox");
    await userEvent.clear(textarea);
    await userEvent.type(textarea, "手で書き直した");
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSend).toHaveBeenCalledWith("手で書き直した", undefined, undefined);
  });

  it("disables sending while transcribing", async () => {
    mocks.voice.status = "transcribing";
    render(<Harness onSend={vi.fn()} />);

    await userEvent.type(screen.getByRole("textbox"), "途中");

    expect(screen.getByRole("button", { name: "送信" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "文字起こし中" })).toBeDisabled();
  });

  it("shows the recording time and stops on demand", async () => {
    mocks.voice.status = "recording";
    mocks.voice.elapsedSeconds = 65;
    render(<Harness onSend={vi.fn()} />);

    expect(screen.getByText("1:05 / 5:00")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "録音を停止" }));

    expect(mocks.voice.stop).toHaveBeenCalled();
  });

  it("shows the error with a retry button", async () => {
    mocks.voice.error = "文字起こしに失敗しました。再試行してください";
    mocks.voice.canRetry = true;
    render(<Harness onSend={vi.fn()} />);

    expect(
      screen.getByText("文字起こしに失敗しました。再試行してください"),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "再試行" }));

    expect(mocks.voice.retry).toHaveBeenCalled();
  });

  it("does not attach a transcript when the user selects everything and types over it", async () => {
    const onSend = vi.fn();
    render(<Harness onSend={onSend} />);

    act(() => mocks.onTranscript!("二分探索は半分にしぼる手法です。"));
    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "ハッシュ表は平均で一定時間です。", {
      initialSelectionStart: 0,
      initialSelectionEnd: "二分探索は半分にしぼる手法です。".length,
    });
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSend).toHaveBeenCalledWith(
      "ハッシュ表は平均で一定時間です。",
      undefined,
      undefined,
    );
  });

  it("keeps the raw transcript when only a misheard word is corrected", async () => {
    const onSend = vi.fn();
    render(<Harness onSend={onSend} />);

    act(() => mocks.onTranscript!("二分探索は半分にしぼる"));
    await userEvent.type(screen.getByRole("textbox"), "絞", {
      initialSelectionStart: 8,
      initialSelectionEnd: 11,
    });
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSend).toHaveBeenCalledWith(
      "二分探索は半分に絞",
      undefined,
      "二分探索は半分にしぼる",
    );
  });

  it("does not attach a transcript when the input is replaced from outside", async () => {
    const onSend = vi.fn();
    render(<ReplaceableHarness onSend={onSend} />);

    act(() => mocks.onTranscript!("新しく話した内容"));
    await userEvent.click(
      screen.getByRole("button", { name: "外から差し替え" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSend).toHaveBeenCalledWith(
      "以前の発言を直したい",
      undefined,
      undefined,
    );
  });
});
