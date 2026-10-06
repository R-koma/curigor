import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TopicCorrectionConfirm } from "@/components/chat/topic-correction-confirm";

describe("TopicCorrectionConfirm", () => {
  it("answers accept with the yes button", async () => {
    const onAnswer = vi.fn().mockReturnValue(true);
    render(<TopicCorrectionConfirm onAnswer={onAnswer} />);

    await userEvent.click(
      screen.getByRole("button", { name: "はい、変更する" }),
    );

    expect(onAnswer).toHaveBeenCalledExactlyOnceWith("accept");
  });

  it("answers decline with the no button", async () => {
    const onAnswer = vi.fn().mockReturnValue(true);
    render(<TopicCorrectionConfirm onAnswer={onAnswer} />);

    await userEvent.click(screen.getByRole("button", { name: "いいえ" }));

    expect(onAnswer).toHaveBeenCalledExactlyOnceWith("decline");
  });

  it("answers only once even if both are clicked", async () => {
    const onAnswer = vi.fn().mockReturnValue(true);
    render(<TopicCorrectionConfirm onAnswer={onAnswer} />);

    await userEvent.click(
      screen.getByRole("button", { name: "はい、変更する" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "いいえ" }));

    expect(onAnswer).toHaveBeenCalledTimes(1);
  });

  it("disables both buttons while a response is loading", () => {
    render(
      <TopicCorrectionConfirm
        disabled
        onAnswer={vi.fn().mockReturnValue(true)}
      />,
    );

    expect(
      screen.getByRole("button", { name: "はい、変更する" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "いいえ" })).toBeDisabled();
  });

  it("lets the user answer again when the answer could not be sent", async () => {
    const onAnswer = vi.fn().mockReturnValueOnce(false).mockReturnValue(true);
    render(<TopicCorrectionConfirm onAnswer={onAnswer} />);

    await userEvent.click(
      screen.getByRole("button", { name: "はい、変更する" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "はい、変更する" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "いいえ" }));

    expect(onAnswer).toHaveBeenCalledTimes(2);
    expect(onAnswer).toHaveBeenLastCalledWith("accept");
  });
});
