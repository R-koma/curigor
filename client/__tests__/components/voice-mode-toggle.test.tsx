import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { VoiceModeToggle } from "@/components/chat/voice-mode-toggle";

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

describe("VoiceModeToggle", () => {
  it("reflects the state and toggles on click", async () => {
    const onChange = vi.fn();
    render(
      <VoiceModeToggle enabled={false} onChange={onChange} error={null} />,
    );

    const toggle = screen.getByRole("switch", { name: "音声モード" });
    expect(toggle).toHaveAttribute("aria-checked", "false");

    await userEvent.click(toggle);

    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("reports the error as a toast", () => {
    render(
      <VoiceModeToggle
        enabled
        onChange={vi.fn()}
        error="読み上げに失敗しました"
      />,
    );

    expect(toast.error).toHaveBeenCalledWith(
      "読み上げに失敗しました",
      expect.objectContaining({ duration: 5000 }),
    );
  });

  it("offers a stop button only while reading aloud", async () => {
    const onStop = vi.fn();
    const { rerender } = render(
      <VoiceModeToggle
        enabled
        onChange={vi.fn()}
        error={null}
        speaking={false}
        onStop={onStop}
      />,
    );
    expect(
      screen.queryByRole("button", { name: "読み上げを停止" }),
    ).not.toBeInTheDocument();

    rerender(
      <VoiceModeToggle
        enabled
        onChange={vi.fn()}
        error={null}
        speaking
        onStop={onStop}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "読み上げを停止" }),
    );

    expect(onStop).toHaveBeenCalledTimes(1);
  });
});
