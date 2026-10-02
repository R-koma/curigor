import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VoiceRecordingBar } from "@/components/chat/voice-recording-bar";

vi.mock("@/hooks/use-audio-levels", () => ({
  useAudioLevels: (_stream: MediaStream | null, count: number) =>
    Array.from({ length: count }, () => 0),
}));

function renderBar(onCancel = vi.fn()) {
  render(
    <VoiceRecordingBar
      elapsedSeconds={0}
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
