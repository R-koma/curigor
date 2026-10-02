import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VoiceRecordingBar } from "@/components/chat/voice-recording-bar";

vi.mock("@/hooks/use-audio-history", () => ({
  useAudioHistory: () => [],
}));

function renderBar(onCancel = vi.fn(), elapsedSeconds = 0) {
  render(
    <VoiceRecordingBar
      elapsedSeconds={elapsedSeconds}
      stream={null}
      onCancel={onCancel}
      onConfirm={vi.fn()}
    />,
  );
  return onCancel;
}

afterEach(() => {
  document.body.innerHTML = "";
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
    const onCancel = renderBar();

    await userEvent.keyboard("{Escape}");

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("leaves Escape alone when another layer already handled it", async () => {
    const closeOtherLayer = (event: KeyboardEvent) => event.preventDefault();
    document.addEventListener("keydown", closeOtherLayer, true);
    const onCancel = renderBar();

    await userEvent.keyboard("{Escape}");
    document.removeEventListener("keydown", closeOtherLayer, true);

    expect(onCancel).not.toHaveBeenCalled();
  });

  it("leaves Escape alone while an input method is composing", () => {
    const onCancel = renderBar();

    fireEvent.keyDown(window, { key: "Escape", isComposing: true });

    expect(onCancel).not.toHaveBeenCalled();
  });

  it("stops listening after it unmounts", async () => {
    const onCancel = vi.fn();
    const { unmount } = render(
      <VoiceRecordingBar
        elapsedSeconds={0}
        stream={null}
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />,
    );

    unmount();
    await userEvent.keyboard("{Escape}");

    expect(onCancel).not.toHaveBeenCalled();
    expect(screen.queryByRole("img")).toBeNull();
  });
});
