import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MessageSpeechButton } from "@/components/chat/message-speech-button";

describe("MessageSpeechButton", () => {
  it("plays the message when idle", async () => {
    const onPlay = vi.fn();
    render(
      <MessageSpeechButton speaking={false} onPlay={onPlay} onStop={vi.fn()} />,
    );

    await userEvent.click(screen.getByRole("button", { name: "読み上げる" }));

    expect(onPlay).toHaveBeenCalledTimes(1);
  });

  it("stops the message while it is being read", async () => {
    const onStop = vi.fn();
    render(<MessageSpeechButton speaking onPlay={vi.fn()} onStop={onStop} />);

    await userEvent.click(
      screen.getByRole("button", { name: "読み上げを停止" }),
    );

    expect(onStop).toHaveBeenCalledTimes(1);
  });
});
