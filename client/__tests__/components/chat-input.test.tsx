import { beforeEach, describe, it, expect, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { toast } from "sonner";
import { ChatInput } from "@/components/chat/chat-input";
import { SEND_FAILED_MESSAGE } from "@/hooks/use-chat-websocket";
import type { VoiceRecorder } from "@/hooks/use-voice-recorder";
import { COARSE_POINTER, setMediaQuery } from "../stubs/match-media";

const mocks = vi.hoisted(() => ({
  voice: null as unknown as VoiceRecorder,
  onTranscript: null as ((text: string) => void) | null,
}));

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

vi.mock("@/hooks/use-voice-recorder", () => ({
  useVoiceRecorder: (options: { onTranscript: (text: string) => void }) => {
    mocks.onTranscript = options.onTranscript;
    return mocks.voice;
  },
}));

vi.mock("@/components/chat/math-editor", () => ({
  MathEditor: ({
    initialValue,
    onChange,
    onSubmit,
  }: {
    initialValue: string;
    onChange: (value: string) => void;
    onSubmit: () => void;
  }) => (
    <input
      aria-label="数式"
      defaultValue={initialValue}
      onChange={(event) => onChange(event.target.value)}
      onKeyDown={(event) => event.key === "Enter" && onSubmit()}
    />
  ),
}));

vi.mock("@/components/chat/code-editor", () => ({
  CodeEditor: ({ onChange }: { onChange: (value: string) => void }) => (
    <textarea
      aria-label="コード"
      className="cm-editor"
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

beforeEach(() => {
  mocks.voice = {
    status: "idle",
    elapsedSeconds: 0,
    error: null,
    canRetry: false,
    stream: null,
    start: vi.fn(),
    stop: vi.fn(),
    cancel: vi.fn(),
    retry: vi.fn(),
  };
  mocks.onTranscript = null;
});

function Harness({
  onSend,
  sessionId = "session-1",
  allowVoice = true,
  allowRichInput = false,
  initialValue = "",
}: {
  onSend: (content: string, images?: unknown, rawTranscript?: string) => void;
  sessionId?: string | null;
  allowVoice?: boolean;
  allowRichInput?: boolean;
  initialValue?: string;
}) {
  const [value, setValue] = useState(initialValue);
  return (
    <ChatInput
      value={value}
      onChange={setValue}
      onSend={onSend}
      isLoading={false}
      sessionId={sessionId}
      allowVoice={allowVoice}
      allowRichInput={allowRichInput}
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
  it("explains the plus button, and hides the tooltip while its menu is open", async () => {
    render(<Harness onSend={vi.fn()} />);

    const plus = screen.getByRole("button", { name: "追加" });
    await userEvent.hover(plus);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("追加");

    await userEvent.click(plus);
    expect(plus).toHaveAttribute("aria-expanded", "true");
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("explains the send and microphone buttons with a tooltip on hover", async () => {
    render(<Harness onSend={vi.fn()} />);

    await userEvent.hover(screen.getByRole("button", { name: "音声で入力" }));
    expect(await screen.findByRole("tooltip")).toHaveTextContent("音声で入力");

    await userEvent.type(screen.getByRole("textbox"), "あ");
    await userEvent.hover(screen.getByRole("button", { name: "送信" }));
    expect(await screen.findByRole("tooltip")).toHaveTextContent("送信");
  });

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
    expect(screen.getByRole("button", { name: "音声で入力" })).toBeDisabled();
  });

  it("confirms on demand without showing the elapsed time", async () => {
    mocks.voice.status = "recording";
    mocks.voice.elapsedSeconds = 65;
    render(<Harness onSend={vi.fn()} />);

    expect(screen.queryByText("1:05 / 5:00")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "録音を確定" }));

    expect(mocks.voice.stop).toHaveBeenCalled();
  });

  it("reports the error as a toast with a retry action", async () => {
    mocks.voice.error = "文字起こしに失敗しました。再試行してください";
    mocks.voice.canRetry = true;
    render(<Harness onSend={vi.fn()} />);

    expect(toast.error).toHaveBeenCalledWith(
      "文字起こしに失敗しました。再試行してください",
      expect.objectContaining({
        action: expect.objectContaining({ label: expect.anything() }),
      }),
    );

    const [, options] = vi.mocked(toast.error).mock.calls[0];
    (options?.action as unknown as { onClick: () => void }).onClick();

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

  it("replaces the input with the recording bar while recording", () => {
    mocks.voice.status = "recording";
    render(<Harness onSend={vi.fn()} />);

    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("button", { name: "送信" })).toBeNull();
    expect(screen.getByRole("img", { name: "音声の波形" })).toBeInTheDocument();
  });

  it("cancels the recording with the cancel button", async () => {
    mocks.voice.status = "recording";
    render(<Harness onSend={vi.fn()} />);

    await userEvent.click(
      screen.getByRole("button", { name: "録音を取り消す" }),
    );

    expect(mocks.voice.cancel).toHaveBeenCalled();
    expect(mocks.voice.stop).not.toHaveBeenCalled();
  });

  it("cancels the recording with the Escape key", async () => {
    mocks.voice.status = "recording";
    render(<Harness onSend={vi.fn()} />);

    await userEvent.keyboard("{Escape}");

    expect(mocks.voice.cancel).toHaveBeenCalled();
  });

  it("keeps typed text hidden while recording and appends the transcript after", async () => {
    const onSend = vi.fn();
    const { rerender } = render(<Harness onSend={onSend} />);
    await userEvent.type(screen.getByRole("textbox"), "前置き");

    mocks.voice.status = "recording";
    rerender(<Harness onSend={onSend} />);
    expect(screen.queryByRole("textbox")).toBeNull();

    mocks.voice.status = "idle";
    rerender(<Harness onSend={onSend} />);
    act(() => mocks.onTranscript!("話した内容"));

    expect(screen.getByRole("textbox")).toHaveValue("前置き\n話した内容");
  });

  it("shows a single status for transcribing", () => {
    mocks.voice.status = "transcribing";
    render(<Harness onSend={vi.fn()} />);

    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(screen.getByRole("status")).toHaveTextContent("文字起こし中…");
    expect(screen.getByRole("button", { name: "音声で入力" })).toBeDisabled();
  });

  it("shows a status while waiting for the microphone permission", () => {
    mocks.voice.status = "starting";
    render(<Harness onSend={vi.fn()} />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "マイクの許可を待っています…",
    );
    expect(screen.getByRole("button", { name: "音声で入力" })).toBeDisabled();
  });

  it("keeps the recording bar, disabled, while stopping", () => {
    mocks.voice.status = "stopping";
    render(<Harness onSend={vi.fn()} />);

    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByRole("button", { name: "録音を確定" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "録音を取り消す" }),
    ).toBeDisabled();
  });

  it("cannot send while the microphone is starting or stopping", async () => {
    mocks.voice.status = "starting";
    render(<Harness onSend={vi.fn()} />);

    await userEvent.type(screen.getByRole("textbox"), "途中");

    expect(screen.getByRole("button", { name: "送信" })).toBeDisabled();
  });

  it("spins the status indicator only when motion is allowed", () => {
    mocks.voice.status = "transcribing";
    render(<Harness onSend={vi.fn()} />);

    const spinner = screen.getByRole("status").querySelector("svg");
    expect(spinner).not.toBeNull();
    expect(spinner).toHaveClass("motion-safe:animate-spin");
    expect(spinner).not.toHaveClass("animate-spin");
  });
});

function VoiceModeHarness({
  onSend,
  isLoading = false,
  initialValue = "",
  restoredTranscript = null,
  onVoiceStart,
}: {
  onSend: (
    content: string,
    images?: unknown,
    rawTranscript?: string,
    autoSent?: boolean,
  ) => void;
  isLoading?: boolean;
  initialValue?: string;
  restoredTranscript?: { text: string; autoSent?: boolean } | null;
  onVoiceStart?: () => void;
}) {
  const [value, setValue] = useState(initialValue);
  return (
    <ChatInput
      value={value}
      onChange={setValue}
      onSend={onSend}
      isLoading={isLoading}
      sessionId="session-1"
      allowVoice
      restoredTranscript={restoredTranscript}
      onVoiceStart={onVoiceStart}
    />
  );
}

describe("ChatInput in voice mode", () => {
  it("puts the dictated transcript in the box without sending", () => {
    const onSend = vi.fn();
    render(<VoiceModeHarness onSend={onSend} />);

    act(() => mocks.onTranscript?.("カードへの回答です"));

    expect(onSend).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox")).toHaveValue("カードへの回答です");
  });

  it("calls onVoiceStart when the mic is pressed", async () => {
    const onVoiceStart = vi.fn();
    render(<VoiceModeHarness onSend={vi.fn()} onVoiceStart={onVoiceStart} />);

    await userEvent.click(screen.getByRole("button", { name: "音声で入力" }));

    expect(onVoiceStart).toHaveBeenCalledTimes(1);
    expect(mocks.voice.start).toHaveBeenCalled();
  });

  it("keeps the restored transcript as raw_transcript when the fixed text is resent", async () => {
    const onSend = vi.fn();
    const { rerender } = render(
      <VoiceModeHarness onSend={onSend} initialValue="二分探索は半分に絞る" />,
    );

    rerender(
      <VoiceModeHarness
        onSend={onSend}
        initialValue="二分探索は半分に絞る"
        restoredTranscript={{ text: "二分探索は半分にしぼる" }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSend).toHaveBeenCalledWith(
      "二分探索は半分に絞る",
      undefined,
      "二分探索は半分にしぼる",
    );
  });

  it("resends a restored auto-sent message as auto-sent so the correction is measurable", async () => {
    const onSend = vi.fn();
    const { rerender } = render(
      <VoiceModeHarness onSend={onSend} initialValue="二分探索は半分に絞る" />,
    );

    rerender(
      <VoiceModeHarness
        onSend={onSend}
        initialValue="二分探索は半分に絞る"
        restoredTranscript={{
          text: "二分探索は半分にしぼる",
          autoSent: true,
        }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSend).toHaveBeenCalledWith(
      "二分探索は半分に絞る",
      undefined,
      "二分探索は半分にしぼる",
      true,
    );
  });

  it("does not carry the auto-sent flag into the next message", async () => {
    const onSend = vi.fn();
    const { rerender } = render(
      <VoiceModeHarness onSend={onSend} initialValue="直した本文" />,
    );
    rerender(
      <VoiceModeHarness
        onSend={onSend}
        initialValue="直した本文"
        restoredTranscript={{ text: "元の文字起こし", autoSent: true }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "送信" }));
    onSend.mockClear();

    await userEvent.clear(screen.getByRole("textbox"));
    await userEvent.type(screen.getByRole("textbox"), "次の発言");
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(onSend).toHaveBeenCalledWith("次の発言", undefined, undefined);
  });

  it("reports a manual send that could not be delivered", async () => {
    const onSend = vi.fn().mockReturnValue(false);
    render(<VoiceModeHarness onSend={onSend} />);

    await userEvent.type(screen.getByRole("textbox"), "手で書いた");
    await userEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(screen.getByRole("textbox")).toHaveValue("手で書いた");
    expect(toast.error).toHaveBeenCalledWith(
      SEND_FAILED_MESSAGE,
      expect.anything(),
    );
  });
});

describe("ChatInput voice conversation button", () => {
  it("shows the voice conversation button and starts it", () => {
    const onStartConversation = vi.fn();
    render(
      <ChatInput
        value=""
        onChange={() => {}}
        onSend={() => true}
        isLoading={false}
        allowVoice
        onStartConversation={onStartConversation}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "声で話す" }));
    expect(onStartConversation).toHaveBeenCalled();
  });

  it("hides the voice conversation button without the handler", () => {
    render(
      <ChatInput
        value=""
        onChange={() => {}}
        onSend={() => true}
        isLoading={false}
        allowVoice
      />,
    );
    expect(screen.queryByRole("button", { name: "声で話す" })).toBeNull();
  });
});

describe("ChatInput mounted with a restored transcript", () => {
  const mountWith = (
    onSend: (
      content: string,
      images?: unknown,
      rawTranscript?: string,
      autoSent?: boolean,
    ) => void,
    restoredTranscript: { text: string; autoSent?: boolean } | null,
  ) =>
    render(
      <ChatInput
        value="二分探索は半分に絞る"
        onChange={() => {}}
        onSend={onSend}
        isLoading={false}
        allowVoice
        restoredTranscript={restoredTranscript}
      />,
    );

  it("sends the restored transcript as raw_transcript", async () => {
    const onSend = vi.fn();
    mountWith(onSend, { text: "二分探索は半分に絞る", autoSent: false });
    await userEvent.click(screen.getByRole("button", { name: "送信" }));
    expect(onSend).toHaveBeenCalledWith(
      "二分探索は半分に絞る",
      undefined,
      "二分探索は半分に絞る",
    );
  });

  it("keeps the auto-sent flag of a restore present at mount", async () => {
    const onSend = vi.fn();
    mountWith(onSend, { text: "二分探索は半分に絞る", autoSent: true });
    await userEvent.click(screen.getByRole("button", { name: "送信" }));
    expect(onSend).toHaveBeenCalledWith(
      "二分探索は半分に絞る",
      undefined,
      "二分探索は半分に絞る",
      true,
    );
  });

  it("sends no raw transcript when mounted without a restore", async () => {
    const onSend = vi.fn();
    mountWith(onSend, null);
    await userEvent.click(screen.getByRole("button", { name: "送信" }));
    expect(onSend).toHaveBeenCalledWith(
      "二分探索は半分に絞る",
      undefined,
      undefined,
    );
  });

  it("sends on Enter with a fine pointer", async () => {
    const onSend = vi.fn();
    render(<Harness onSend={onSend} />);
    await userEvent.type(screen.getByRole("textbox"), "説明します{Enter}");
    expect(onSend).toHaveBeenCalledOnce();
    expect(onSend.mock.calls[0][0]).toBe("説明します");
  });

  it("inserts a newline on Enter with a coarse pointer and sends only from the button", async () => {
    setMediaQuery(COARSE_POINTER, true);
    const onSend = vi.fn();
    render(<Harness onSend={onSend} />);
    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "一行目{Enter}二行目");
    expect(onSend).not.toHaveBeenCalled();
    expect(textarea).toHaveValue("一行目\n二行目");
    await userEvent.click(screen.getByRole("button", { name: "送信" }));
    expect(onSend).toHaveBeenCalledOnce();
  });

  it("gives the buttons a 44px target on a coarse pointer", () => {
    render(
      <ChatInput
        value=""
        onChange={vi.fn()}
        onSend={vi.fn()}
        isLoading={false}
        sessionId="session-1"
        allowVoice
        onStartConversation={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "音声で入力" }).className,
    ).toContain("pointer-coarse:size-11");
    expect(
      screen.getByRole("button", { name: "声で話す" }).className,
    ).toContain("pointer-coarse:size-11");
  });
});

describe("ChatInput rich input", () => {
  const textbox = () => screen.getByPlaceholderText("入力...");

  async function openMenuItem(name: string) {
    await userEvent.click(screen.getByRole("button", { name: "追加" }));
    await userEvent.click(screen.getByRole("button", { name }));
  }

  it("offers formulas and code next to images", async () => {
    render(<Harness onSend={vi.fn()} allowRichInput />);

    await userEvent.click(screen.getByRole("button", { name: "追加" }));

    for (const name of ["画像を追加", "数式を挿入", "コードを挿入"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("offers formulas and code where images are not allowed", async () => {
    const { container } = render(
      <ChatInput
        value=""
        onChange={vi.fn()}
        onSend={vi.fn()}
        isLoading={false}
        allowImages={false}
        allowRichInput
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "追加" }));

    expect(
      screen.getByRole("button", { name: "数式を挿入" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "画像を追加" })).toBeNull();
    expect(container.querySelector('input[type="file"]')).toBeNull();
  });

  it("hides the plus button when there is nothing to add", () => {
    render(
      <ChatInput
        value=""
        onChange={vi.fn()}
        onSend={vi.fn()}
        isLoading={false}
        allowImages={false}
      />,
    );

    expect(screen.queryByRole("button", { name: "追加" })).toBeNull();
  });

  it("inserts a formula at the cursor and returns focus", async () => {
    render(<Harness onSend={vi.fn()} allowRichInput />);
    await userEvent.type(textbox(), "答えは");

    await openMenuItem("数式を挿入");
    await userEvent.type(screen.getByLabelText("数式"), "x^2");
    await userEvent.click(screen.getByRole("button", { name: "挿入" }));

    expect(textbox()).toHaveValue("答えは $x^2$");
    expect(screen.queryByLabelText("数式")).toBeNull();
    expect(textbox()).toHaveFocus();
  });

  it("edits the formula under the cursor", async () => {
    render(
      <Harness
        onSend={vi.fn()}
        allowRichInput
        initialValue={"面積は $\\pi r^2$ です"}
      />,
    );
    (textbox() as HTMLTextAreaElement).setSelectionRange(8, 8);

    await openMenuItem("数式を挿入");
    const field = screen.getByLabelText("数式");
    expect(field).toHaveValue("\\pi r^2");
    await userEvent.clear(field);
    await userEvent.type(field, "2\\pi r");
    await userEvent.click(screen.getByRole("button", { name: "挿入" }));

    expect(textbox()).toHaveValue("面積は $2\\pi r$ です");
  });

  it("replaces the formula being edited even after typing before it", async () => {
    render(<Harness onSend={vi.fn()} allowRichInput initialValue="x $a$ y" />);
    (textbox() as HTMLTextAreaElement).setSelectionRange(3, 3);

    await openMenuItem("数式を挿入");
    await userEvent.type(textbox(), "z", {
      initialSelectionStart: 0,
      initialSelectionEnd: 0,
    });
    const field = screen.getByLabelText("数式");
    await userEvent.clear(field);
    await userEvent.type(field, "b");
    await userEvent.click(screen.getByRole("button", { name: "挿入" }));

    expect(textbox()).toHaveValue("zx $b$ y");
  });

  it("inserts code as a block on its own lines", async () => {
    render(<Harness onSend={vi.fn()} allowRichInput />);
    await userEvent.type(textbox(), "見て");

    await openMenuItem("コードを挿入");
    await userEvent.selectOptions(screen.getByLabelText("言語"), "python");
    await userEvent.type(screen.getByLabelText("コード"), "print(1)");
    await userEvent.click(screen.getByRole("button", { name: "挿入" }));

    expect(textbox()).toHaveValue("見て\n```python\nprint(1)\n```\n");
  });

  it("inserts where the cursor is now, not where it was when opened", async () => {
    render(<Harness onSend={vi.fn()} allowRichInput />);
    await userEvent.type(textbox(), "a");

    await openMenuItem("数式を挿入");
    await userEvent.type(textbox(), " b");
    await userEvent.type(screen.getByLabelText("数式"), "x");
    await userEvent.click(screen.getByRole("button", { name: "挿入" }));

    expect(textbox()).toHaveValue("a b $x$");
  });

  it("closes the panel with Escape without inserting", async () => {
    render(<Harness onSend={vi.fn()} allowRichInput />);

    await openMenuItem("数式を挿入");
    await userEvent.type(screen.getByLabelText("数式"), "x{Escape}");

    expect(screen.queryByLabelText("数式")).toBeNull();
    expect(textbox()).toHaveValue("");
  });

  it("does not send while a panel is open", async () => {
    const onSend = vi.fn();
    render(<Harness onSend={onSend} allowRichInput />);
    await userEvent.type(textbox(), "hi");

    await openMenuItem("コードを挿入");
    await userEvent.type(textbox(), "{Enter}");

    expect(screen.getByRole("button", { name: "送信" })).toBeDisabled();
    expect(onSend).not.toHaveBeenCalled();
  });

  it("closes the panel when voice input starts", async () => {
    render(<Harness onSend={vi.fn()} allowRichInput />);

    await openMenuItem("数式を挿入");
    await userEvent.click(screen.getByRole("button", { name: "音声で入力" }));

    expect(screen.queryByLabelText("数式")).toBeNull();
  });

  function pasteInto(element: HTMLElement, text: string, vscode = "") {
    return fireEvent.paste(element, {
      clipboardData: {
        getData: (type: string) =>
          type === "text/plain"
            ? text
            : type === "vscode-editor-data"
              ? vscode
              : "",
      },
    });
  }

  const code = "def add(a, b):\n    return a + b\n";
  const vscode = JSON.stringify({ mode: "python" });

  it("fences pasted code and lets the paste be undone", async () => {
    render(<Harness onSend={vi.fn()} allowRichInput />);

    pasteInto(textbox(), code, vscode);

    expect(textbox()).toHaveValue(
      "```python\ndef add(a, b):\n    return a + b\n```\n",
    );
    expect(screen.getByText("コードとして囲みました")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "元に戻す" }));

    expect(textbox()).toHaveValue(code);
    expect(screen.queryByText("コードとして囲みました")).toBeNull();
  });

  it("announces the fenced paste", () => {
    render(<Harness onSend={vi.fn()} allowRichInput />);

    pasteInto(textbox(), code, vscode);

    expect(
      screen.getByText("コードとして囲みました").closest('[role="status"]'),
    ).not.toBeNull();
  });

  it("drops the undo offer when a formula is inserted", async () => {
    render(<Harness onSend={vi.fn()} allowRichInput />);

    pasteInto(textbox(), code, vscode);
    await openMenuItem("数式を挿入");
    await userEvent.type(screen.getByLabelText("数式"), "x");
    await userEvent.click(screen.getByRole("button", { name: "挿入" }));

    expect(screen.queryByText("コードとして囲みました")).toBeNull();
  });

  it("drops the undo offer after the next edit", async () => {
    render(<Harness onSend={vi.fn()} allowRichInput />);

    pasteInto(textbox(), code, vscode);
    await userEvent.type(textbox(), "a");

    expect(screen.queryByText("コードとして囲みました")).toBeNull();
  });

  it("leaves pasted prose to the browser", () => {
    render(<Harness onSend={vi.fn()} allowRichInput />);

    const notPrevented = pasteInto(textbox(), "一行目です。\n二行目です。");

    expect(notPrevented).toBe(true);
    expect(screen.queryByText("コードとして囲みました")).toBeNull();
  });

  it("previews formulas and hides the preview while a panel is open", async () => {
    render(<Harness onSend={vi.fn()} allowRichInput />);
    await userEvent.type(textbox(), "答えは $x^2$");

    expect(
      await screen.findByRole("region", { name: "表示の確認" }),
    ).toBeInTheDocument();

    await openMenuItem("数式を挿入");

    expect(screen.queryByRole("region", { name: "表示の確認" })).toBeNull();
  });
});
