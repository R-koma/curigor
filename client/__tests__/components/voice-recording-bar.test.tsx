import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VoiceRecordingBar } from "@/components/chat/voice-recording-bar";

const mocks = vi.hoisted(() => ({ history: [] as number[] }));

vi.mock("@/hooks/use-audio-history", () => ({
  useAudioHistory: () => mocks.history,
}));

function renderBar(onCancel = vi.fn(), elapsedSeconds = 0, busy = false) {
  const onConfirm = vi.fn();
  render(
    <VoiceRecordingBar
      elapsedSeconds={elapsedSeconds}
      stream={null}
      busy={busy}
      onCancel={onCancel}
      onConfirm={onConfirm}
    />,
  );
  return { onCancel, onConfirm };
}

afterEach(() => {
  mocks.history = [];
});

describe("VoiceRecordingBar", () => {
  it("does not show the elapsed time while there is plenty left", () => {
    renderBar(vi.fn(), 42);

    expect(screen.queryByText(/\d:\d\d/)).toBeNull();
    expect(screen.queryByText(/自動で確定します/)).toBeNull();
  });

  it("puts the warning to the right of the waveform", () => {
    renderBar(vi.fn(), 275);

    const waveform = screen.getByRole("img", { name: "音声の波形" });
    const warning = screen.getByText("あと 25 秒で自動で確定します");
    expect(
      waveform.compareDocumentPosition(warning) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("warns that the recording will be confirmed on its own near the limit", () => {
    renderBar(vi.fn(), 275);

    expect(
      screen.getByText("あと 25 秒で自動で確定します"),
    ).toBeInTheDocument();
  });

  it("cancels on Escape", async () => {
    const { onCancel } = renderBar();

    await userEvent.keyboard("{Escape}");

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("leaves Escape alone when another layer already handled it", async () => {
    const closeOtherLayer = (event: KeyboardEvent) => event.preventDefault();
    document.addEventListener("keydown", closeOtherLayer, true);
    const { onCancel } = renderBar();

    await userEvent.keyboard("{Escape}");
    document.removeEventListener("keydown", closeOtherLayer, true);

    expect(onCancel).not.toHaveBeenCalled();
  });

  it("leaves Escape alone while an input method is composing", () => {
    const { onCancel } = renderBar();

    fireEvent.keyDown(window, { key: "Escape", isComposing: true });

    expect(onCancel).not.toHaveBeenCalled();
  });

  it("stops listening after it unmounts", async () => {
    const onCancel = vi.fn();
    const { unmount } = render(
      <VoiceRecordingBar
        elapsedSeconds={0}
        stream={null}
        busy={false}
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />,
    );

    unmount();
    await userEvent.keyboard("{Escape}");

    expect(onCancel).not.toHaveBeenCalled();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("tells the user when nothing has been heard for a while", () => {
    mocks.history = Array.from({ length: 60 }, () => 0);
    renderBar();

    expect(
      screen.getByText("声が聞こえません。マイクを確認してください"),
    ).toBeInTheDocument();
  });

  it("does not say so while a voice is coming in", () => {
    mocks.history = Array.from({ length: 60 }, (_, i) => (i === 59 ? 0.5 : 0));
    renderBar();

    expect(screen.queryByText(/声が聞こえません/)).toBeNull();
  });

  it("stays quiet when the audio analysis is unavailable", () => {
    mocks.history = [];
    renderBar();

    expect(screen.queryByText(/声が聞こえません/)).toBeNull();
  });

  it("disables both buttons while stopping", () => {
    renderBar(vi.fn(), 0, true);

    expect(
      screen.getByRole("button", { name: "録音を取り消す" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "録音を確定" })).toBeDisabled();
  });

  it("does not cancel on Escape while stopping", async () => {
    const { onCancel } = renderBar(vi.fn(), 0, true);

    await userEvent.keyboard("{Escape}");

    expect(onCancel).not.toHaveBeenCalled();
  });

  it("explains the buttons, including the Escape shortcut", async () => {
    renderBar();

    await userEvent.tab();
    expect(await screen.findAllByText("取り消し（Esc）")).not.toHaveLength(0);

    await userEvent.tab();
    expect(await screen.findAllByText("確定して文字起こし")).not.toHaveLength(
      0,
    );
  });

  it("fades in when it appears", () => {
    renderBar();

    expect(screen.getByTestId("voice-recording-bar")).toHaveClass(
      "motion-safe:animate-in",
    );
  });

  it("cancels with one Escape even while a button tooltip is open", async () => {
    const { onCancel } = renderBar();

    await userEvent.tab();
    expect(await screen.findAllByText("取り消し（Esc）")).not.toHaveLength(0);
    await userEvent.keyboard("{Escape}");

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("cancels with one Escape while hovering a button", async () => {
    const { onCancel } = renderBar();

    await userEvent.hover(screen.getByRole("button", { name: "録音を確定" }));
    expect(await screen.findAllByText("確定して文字起こし")).not.toHaveLength(
      0,
    );
    await userEvent.keyboard("{Escape}");

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("does not cancel from a tooltip while stopping", async () => {
    const { onCancel } = renderBar(vi.fn(), 0, true);

    await userEvent.hover(
      screen.getByRole("button", { name: "録音を確定" }).parentElement!,
    );
    await userEvent.keyboard("{Escape}");

    expect(onCancel).not.toHaveBeenCalled();
  });

  it("lets the message shrink so it cannot push the buttons off a narrow screen", () => {
    mocks.history = Array.from({ length: 60 }, () => 0);
    renderBar();

    const message = screen.getByText(
      "声が聞こえません。マイクを確認してください",
    );
    expect(message).toHaveClass("min-w-0");
    expect(message).not.toHaveClass("shrink-0");
  });

  it("does not report silence during a pause once a voice has been heard", () => {
    mocks.history = [0.6, ...Array.from({ length: 60 }, () => 0)];
    const { rerender } = render(
      <VoiceRecordingBar
        elapsedSeconds={5}
        stream={null}
        busy={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.queryByText(/声が聞こえません/)).toBeNull();

    mocks.history = Array.from({ length: 60 }, () => 0);
    rerender(
      <VoiceRecordingBar
        elapsedSeconds={6}
        stream={null}
        busy={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    expect(screen.queryByText(/声が聞こえません/)).toBeNull();
  });
});
