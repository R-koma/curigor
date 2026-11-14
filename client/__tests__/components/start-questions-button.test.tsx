import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StartQuestionsButton } from "@/components/chat/start-questions-button";

describe("StartQuestionsButton", () => {
  it("shows the number of pending questions and starts on click", async () => {
    const onStart = vi.fn();
    render(<StartQuestionsButton count={2} onStart={onStart} />);
    await userEvent.click(
      screen.getByRole("button", { name: "質問を聞く（2）" }),
    );
    expect(onStart).toHaveBeenCalledOnce();
  });
});
