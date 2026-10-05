import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SpeechSpeed } from "@/hooks/use-voice-conversation";
import { VoicePanel } from "@/components/chat/voice-panel";

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

  it.each([
    ["ゆっくり読み上げる", 1],
    ["速く読み上げる", 1.5],
  ] as const)("switches from the default with %s", (name, value) => {
    const props = setup();
    const button = screen.getByRole("button", { name });
    expect(button).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(button);
    expect(props.onSpeedChange).toHaveBeenCalledWith(value);
  });

  it("returns to the default when the pressed speed is clicked again", () => {
    const props = setup({ speed: 1.5 });
    const button = screen.getByRole("button", { name: "速く読み上げる" });
    expect(button).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(button);
    expect(props.onSpeedChange).toHaveBeenCalledWith(1.25);
  });

  it.each([
    [1.25, "ゆっくり読み上げる", "AIの読み上げを遅くする"],
    [1.25, "速く読み上げる", "AIの読み上げを速くする"],
    [1.5, "速く読み上げる", "標準の速さに戻す"],
  ] as const)("at %s explains %s on focus", async (speed, name, hint) => {
    setup({ speed });
    fireEvent.focus(screen.getByRole("button", { name }));
    expect(await screen.findByRole("tooltip")).toHaveTextContent(hint);
  });

  it("switches straight from slow to fast", () => {
    const props = setup({ speed: 1 });
    fireEvent.click(screen.getByRole("button", { name: "速く読み上げる" }));
    expect(props.onSpeedChange).toHaveBeenCalledWith(1.5);
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

  it("explains the review hold while the intake card is shown", () => {
    setup({ holdForReview: true });
    expect(screen.getByText(/入力欄に入ります/)).toBeInTheDocument();
  });

  it("ends the conversation", () => {
    const props = setup();
    fireEvent.click(screen.getByRole("button", { name: "テキストに戻る" }));
    expect(props.onEnd).toHaveBeenCalled();
  });
});

describe("VoicePanel key guards", () => {
  it("leaves Enter to a focused button but still handles Escape and Backspace", () => {
    const props = setup();
    const button = screen.getByRole("button", { name: "速く読み上げる" });
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
