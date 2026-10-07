import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SpeechSpeed } from "@/hooks/use-voice-conversation";
import { VoicePanel } from "@/components/chat/voice-panel";

function baseProps(): Parameters<typeof VoicePanel>[0] {
  return {
    status: "listening",
    segments: [],
    speed: 1.25,
    holdForReview: false,
    onSpeedChange: vi.fn(),
    onPause: vi.fn(),
    onResume: vi.fn(),
    onSendNow: vi.fn(),
    onDiscard: vi.fn(),
    onEnd: vi.fn(),
  };
}

function setup(overrides: Partial<Parameters<typeof VoicePanel>[0]> = {}) {
  const props = {
    status: "listening" as const,
    segments: [],
    speed: 1.25 as SpeechSpeed,
    holdForReview: false,
    onSpeedChange: vi.fn(),
    onPause: vi.fn(),
    onResume: vi.fn(),
    onSendNow: vi.fn(),
    onDiscard: vi.fn(),
    onEnd: vi.fn(),
    ...overrides,
  };
  render(<VoicePanel {...props} />);
  return props;
}

describe("VoicePanel", () => {
  beforeEach(() => {
    localStorage.removeItem("voice-hint-seen");
  });

  it.each([
    ["listening", "聞いています"],
    ["thinking", "考え中"],
    ["speaking", "話しています"],
    ["paused", "一時停止中"],
    ["starting", "マイクを準備しています"],
  ] as const)("shows %s", (status, label) => {
    setup({ status });
    expect(screen.getByRole("status")).toHaveTextContent(label);
  });

  it("shows done, pending and failed segments", () => {
    setup({
      segments: [
        { id: 1, text: "二分探索は", status: "done" },
        { id: 2, text: "", status: "failed" },
        { id: 3, text: "", status: "pending" },
      ],
    });
    expect(screen.getByText("二分探索は")).toBeInTheDocument();
    expect(screen.getByText("（聞き取れませんでした）")).toBeInTheDocument();
    expect(screen.getByLabelText("文字起こし中")).toBeInTheDocument();
  });

  it("does not show the speed as a number", () => {
    setup();
    expect(screen.queryByText(/1\.25|×/)).not.toBeInTheDocument();
  });

  it("keeps the speed inside the settings popover", async () => {
    const props = setup();
    expect(
      screen.queryByRole("group", { name: "読み上げの速さ" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "設定とヒント" }));
    const standard = await screen.findByRole("button", { name: "標準" });
    expect(standard).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "速く" }));
    expect(props.onSpeedChange).toHaveBeenCalledWith(1.5);
    fireEvent.click(screen.getByRole("button", { name: "ゆっくり" }));
    expect(props.onSpeedChange).toHaveBeenCalledWith(1);
  });

  it("handles Enter, Escape and Backspace", () => {
    const props = setup();
    fireEvent.keyDown(window, { key: "Enter" });
    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.keyDown(window, { key: "Backspace" });
    expect(props.onSendNow).toHaveBeenCalled();
    expect(props.onPause).toHaveBeenCalled();
    expect(props.onDiscard).toHaveBeenCalled();
  });

  it("Escape resumes while paused", () => {
    const props = setup({ status: "paused" });
    fireEvent.keyDown(window, { key: "Escape" });
    expect(props.onResume).toHaveBeenCalled();
  });

  it("ignores keys typed into an input", () => {
    const props = setup();
    const input = document.createElement("input");
    document.body.appendChild(input);
    fireEvent.keyDown(input, { key: "Enter" });
    expect(props.onSendNow).not.toHaveBeenCalled();
    input.remove();
  });

  it("explains the review hold while a question with choices is shown", () => {
    setup({ holdForReview: true });
    expect(screen.getByText(/質問への回答は/)).toBeInTheDocument();
    expect(screen.getByText(/入力欄に入ります/)).toBeInTheDocument();
  });

  it("hides the keyboard shortcuts from the always-visible text", () => {
    setup();
    expect(screen.getByText(/「以上」と言うと送信します/)).toBeInTheDocument();
    expect(screen.queryByText(/Backspace で言い直し/)).not.toBeInTheDocument();
  });

  it("hides the send hint after the first send and on later mounts", () => {
    const { unmount, rerender } = render(<VoicePanel {...baseProps()} />);
    expect(screen.getByText(/「以上」と言うと送信します/)).toBeInTheDocument();
    rerender(<VoicePanel {...baseProps()} status="thinking" />);
    expect(
      screen.queryByText(/「以上」と言うと送信します/),
    ).not.toBeInTheDocument();
    unmount();
    render(<VoicePanel {...baseProps()} />);
    expect(
      screen.queryByText(/「以上」と言うと送信します/),
    ).not.toBeInTheDocument();
  });

  it("lists the shortcuts in the help popover", async () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "設定とヒント" }));
    expect(await screen.findByText("Backspace")).toBeInTheDocument();
    expect(screen.getByText("言い直し")).toBeInTheDocument();
  });

  it("shows the Esc shortcut in the pause tooltip", async () => {
    setup();
    fireEvent.focus(screen.getByRole("button", { name: "一時停止" }));
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Esc");
  });

  it("offers send and redo buttons once something is transcribed", () => {
    const empty = setup();
    expect(
      screen.queryByRole("button", { name: /送信/ }),
    ).not.toBeInTheDocument();
    expect(empty.onSendNow).not.toHaveBeenCalled();
  });

  it("sends and redoes with the buttons", () => {
    const props = setup({
      segments: [{ id: 1, text: "二分探索は", status: "done" }],
    });
    fireEvent.click(screen.getByRole("button", { name: "送信" }));
    fireEvent.click(screen.getByRole("button", { name: "言い直す" }));
    expect(props.onSendNow).toHaveBeenCalled();
    expect(props.onDiscard).toHaveBeenCalled();
  });

  it("labels the send button for the review hold", () => {
    setup({
      holdForReview: true,
      segments: [{ id: 1, text: "目的は", status: "done" }],
    });
    expect(
      screen.getByRole("button", { name: "入力欄に入れる" }),
    ).toBeInTheDocument();
  });

  it("prompts the learner while listening with nothing transcribed", () => {
    setup();
    expect(screen.getByText("話しかけてください")).toBeInTheDocument();
  });

  it("shows the waveform only while listening", () => {
    const subscribeLevel = vi.fn(() => () => {});
    setup({ subscribeLevel });
    expect(screen.getByRole("img", { name: "音声の波形" })).toBeInTheDocument();
    expect(subscribeLevel).toHaveBeenCalled();
  });

  it("hides the waveform while the AI is speaking", () => {
    setup({ status: "speaking", subscribeLevel: () => () => {} });
    expect(
      screen.queryByRole("img", { name: "音声の波形" }),
    ).not.toBeInTheDocument();
  });

  it("offers a labelled resume button while paused", () => {
    const props = setup({ status: "paused" });
    fireEvent.click(screen.getByRole("button", { name: "声で話すのを再開" }));
    expect(props.onResume).toHaveBeenCalled();
  });

  it("ends the conversation", () => {
    const props = setup();
    fireEvent.click(screen.getByRole("button", { name: "キーボードで入力" }));
    expect(props.onEnd).toHaveBeenCalled();
  });
});

describe("VoicePanel key guards", () => {
  it("leaves Enter to a focused button but still handles Escape and Backspace", () => {
    const props = setup();
    const button = screen.getByRole("button", { name: "設定とヒント" });
    button.focus();
    fireEvent.keyDown(button, { key: "Enter" });
    expect(props.onSendNow).not.toHaveBeenCalled();
    fireEvent.keyDown(button, { key: "Escape" });
    expect(props.onPause).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(button, { key: "Backspace" });
    expect(props.onDiscard).toHaveBeenCalled();
  });

  it("resumes on Escape from a focused button while paused", () => {
    const props = setup({ status: "paused" });
    fireEvent.keyDown(screen.getByRole("button", { name: "再開" }), {
      key: "Escape",
    });
    expect(props.onResume).toHaveBeenCalled();
  });

  it.each(["input", "textarea"])("ignores every key inside a %s", (tag) => {
    const props = setup();
    const field = document.createElement(tag);
    document.body.appendChild(field);
    for (const key of ["Enter", "Escape", "Backspace"])
      fireEvent.keyDown(field, { key });
    field.remove();
    expect(props.onSendNow).not.toHaveBeenCalled();
    expect(props.onPause).not.toHaveBeenCalled();
    expect(props.onDiscard).not.toHaveBeenCalled();
  });

  it.each(["dialog", "alertdialog", "menu"])(
    "ignores every key inside role=%s",
    (role) => {
      const props = setup();
      const box = document.createElement("div");
      box.setAttribute("role", role);
      const inner = document.createElement("span");
      box.appendChild(inner);
      document.body.appendChild(box);
      for (const key of ["Enter", "Escape", "Backspace"])
        fireEvent.keyDown(inner, { key });
      box.remove();
      expect(props.onSendNow).not.toHaveBeenCalled();
      expect(props.onPause).not.toHaveBeenCalled();
      expect(props.onDiscard).not.toHaveBeenCalled();
    },
  );

  it("ignores Enter while composing", () => {
    const props = setup();
    fireEvent.keyDown(window, { key: "Enter", isComposing: true });
    expect(props.onSendNow).not.toHaveBeenCalled();
  });

  it("stops handling keys after unmount", () => {
    const onSendNow = vi.fn();
    const { unmount } = render(
      <VoicePanel
        status="listening"
        segments={[]}
        speed={1.25}
        holdForReview={false}
        onSpeedChange={vi.fn()}
        onPause={vi.fn()}
        onResume={vi.fn()}
        onSendNow={onSendNow}
        onDiscard={vi.fn()}
        onEnd={vi.fn()}
      />,
    );
    unmount();
    fireEvent.keyDown(window, { key: "Enter" });
    expect(onSendNow).not.toHaveBeenCalled();
  });
});
