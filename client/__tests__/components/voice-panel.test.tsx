import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SpeechSpeed } from "@/hooks/use-voice-conversation";
import { VoicePanel } from "@/components/chat/voice-panel";
import { COARSE_POINTER, setMediaQuery } from "../stubs/match-media";

function baseProps(): Parameters<typeof VoicePanel>[0] {
  return {
    status: "listening",
    segments: [],
    speed: 1.25,
    noInterrupt: false,
    holdForReview: false,
    onSpeedChange: vi.fn(),
    onNoInterruptChange: vi.fn(),
    onStopSpeech: vi.fn(),
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
    noInterrupt: false,
    holdForReview: false,
    onSpeedChange: vi.fn(),
    onNoInterruptChange: vi.fn(),
    onStopSpeech: vi.fn(),
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

  it("keeps the status for screen readers only", () => {
    setup({ status: "paused" });
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("一時停止中");
    expect(status.className).toContain("sr-only");
  });

  it("pauses from the central button while listening", () => {
    const props = setup({ status: "listening" });
    fireEvent.click(screen.getByRole("button", { name: "一時停止" }));
    expect(props.onPause).toHaveBeenCalledTimes(1);
  });

  it("pauses from the central button while the AI is thinking", () => {
    const props = setup({ status: "thinking" });
    fireEvent.click(screen.getByRole("button", { name: "一時停止" }));
    expect(props.onPause).toHaveBeenCalledTimes(1);
  });

  it("resumes from the central button while paused, without extra text", () => {
    const props = setup({ status: "paused" });
    fireEvent.click(screen.getByRole("button", { name: "再開" }));
    expect(props.onResume).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("マイクは止まっています")).toBeNull();
    expect(screen.queryByText("声で話すのを再開")).toBeNull();
    expect(screen.queryByRole("button", { name: "一時停止" })).toBeNull();
  });

  it("stops only the reading from the central button while the AI is speaking", () => {
    const props = setup({ status: "speaking" });
    fireEvent.click(screen.getByRole("button", { name: "読み上げを停止" }));
    expect(props.onStopSpeech).toHaveBeenCalledTimes(1);
    expect(props.onPause).not.toHaveBeenCalled();
  });

  it("cannot be pressed while the microphone is starting", () => {
    const props = setup({ status: "starting" });
    const orb = screen.getByRole("button", { name: "マイクを準備しています" });
    expect(orb).toBeDisabled();
    fireEvent.click(orb);
    expect(props.onPause).not.toHaveBeenCalled();
  });

  it("switches to the keyboard with an icon button", () => {
    const props = setup();
    const keyboard = screen.getByRole("button", { name: "キーボードで入力" });
    expect(keyboard).not.toHaveTextContent("キーボードで入力");
    fireEvent.click(keyboard);
    expect(props.onEnd).toHaveBeenCalledTimes(1);
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

  it.each([
    [false, true],
    [true, false],
  ])(
    "toggles interrupting from the settings popover (on: %s)",
    async (noInterrupt, next) => {
      const props = setup({ noInterrupt });
      fireEvent.click(screen.getByRole("button", { name: "設定とヒント" }));
      const toggle = await screen.findByRole("switch", {
        name: "読み上げ中は割り込まない",
      });
      expect(toggle).toHaveAttribute("aria-checked", String(noInterrupt));
      fireEvent.click(toggle);
      expect(props.onNoInterruptChange).toHaveBeenCalledWith(next);
    },
  );

  it("offers the stop button only while the AI is speaking", () => {
    setup({ status: "listening" });
    expect(
      screen.queryByRole("button", { name: "読み上げを停止" }),
    ).not.toBeInTheDocument();
  });

  it("explains that speech is not heard while reading when interrupting is off", () => {
    setup({ status: "speaking", noInterrupt: true });
    expect(screen.getByText("読み上げ中は聞き取りません")).toBeInTheDocument();
  });

  it("does not show that note while interrupting is allowed", () => {
    setup({ status: "speaking" });
    expect(
      screen.queryByText("読み上げ中は聞き取りません"),
    ).not.toBeInTheDocument();
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
    expect(screen.getByText("「以上」で入力欄に入ります")).toBeInTheDocument();
    expect(screen.queryByText(/質問への回答は/)).toBeNull();
  });

  it("hides the keyboard shortcuts from the always-visible text", () => {
    setup();
    expect(screen.getByText(/「以上」で送信/)).toBeInTheDocument();
    expect(screen.queryByText(/Backspace で言い直し/)).not.toBeInTheDocument();
  });

  it("hides the send hint after the first send and on later mounts", () => {
    const { unmount, rerender } = render(<VoicePanel {...baseProps()} />);
    expect(screen.getByText(/「以上」で送信/)).toBeInTheDocument();
    rerender(<VoicePanel {...baseProps()} status="thinking" />);
    expect(screen.queryByText(/「以上」で送信/)).not.toBeInTheDocument();
    unmount();
    render(<VoicePanel {...baseProps()} />);
    expect(screen.queryByText(/「以上」で送信/)).not.toBeInTheDocument();
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

  it("shows only the first-time hint while listening with nothing transcribed", () => {
    setup();
    expect(screen.getByText("話し終えたら「以上」で送信")).toBeInTheDocument();
    expect(screen.queryByText("話しかけてください")).toBeNull();
    expect(screen.queryByText(/イヤホン/)).toBeNull();
  });

  it("shows no text at all while paused", () => {
    setup({ status: "paused" });
    expect(screen.queryByText(/「以上」で送信/)).toBeNull();
    expect(screen.queryByText(/イヤホン/)).toBeNull();
  });

  it("keeps what was said while paused but offers no send or redo", () => {
    setup({
      status: "paused",
      segments: [{ id: 1, text: "二分探索は", status: "done" }],
    });
    expect(screen.getByText("二分探索は")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "送信" })).toBeNull();
    expect(screen.queryByRole("button", { name: "言い直す" })).toBeNull();
  });

  it("uses icon-only redo and send buttons", () => {
    setup({ segments: [{ id: 1, text: "二分探索は", status: "done" }] });
    expect(
      screen.getByRole("button", { name: "言い直す" }),
    ).not.toHaveTextContent("言い直す");
    expect(screen.getByRole("button", { name: "送信" })).not.toHaveTextContent(
      "送信",
    );
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

  it("recommends earphones first in the settings", async () => {
    setup();
    await userEvent.click(screen.getByRole("button", { name: "設定とヒント" }));
    const advice = await screen.findByText(/イヤホンの利用がおすすめです/);
    const speed = screen.getByText("読み上げの速さ", { selector: "p" });
    expect(
      advice.compareDocumentPosition(speed) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
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
        noInterrupt={false}
        holdForReview={false}
        onSpeedChange={vi.fn()}
        onNoInterruptChange={vi.fn()}
        onStopSpeech={vi.fn()}
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

  const SPOKEN = [{ id: 1, status: "done" as const, text: "再帰とは" }];

  it("sizes its buttons for touch unless the pointer is fine", () => {
    setup({ segments: SPOKEN });
    expect(
      screen.getByRole("button", { name: "設定とヒント" }).className,
    ).toContain("size-11");
    expect(
      screen.getByRole("button", { name: "キーボードで入力" }).className,
    ).toContain("pointer-fine:size-8");
    expect(
      screen.getByRole("button", { name: "一時停止" }).className,
    ).toContain("size-16");
    expect(screen.getByRole("button", { name: "送信" }).className).toContain(
      "size-11",
    );
  });

  it("names the keys in tooltips and lists them in the settings on a fine pointer", async () => {
    setup({ segments: SPOKEN });
    await userEvent.click(screen.getByRole("button", { name: "設定とヒント" }));
    expect(await screen.findByText("Enter")).toBeInTheDocument();
    expect(screen.getByText("Esc")).toBeInTheDocument();
    expect(screen.getByText("Backspace")).toBeInTheDocument();
    expect(screen.getByText("「以上」と言う")).toBeInTheDocument();
  });

  it("drops the key hints on a coarse pointer and keeps the 以上 hint", async () => {
    setMediaQuery(COARSE_POINTER, true);
    setup({ segments: SPOKEN });
    await userEvent.click(screen.getByRole("button", { name: "設定とヒント" }));
    expect(await screen.findByText("「以上」と言う")).toBeInTheDocument();
    expect(screen.queryByText("Enter")).toBeNull();
    expect(screen.queryByText("Esc")).toBeNull();
    expect(screen.queryByText("Backspace")).toBeNull();
  });
});
