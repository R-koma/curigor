import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VoiceIntakePrompt } from "@/components/chat/voice-intake-prompt";
import { ALL_SKIPPED_TEXT, type IntakeCard } from "@/lib/intake";

const card: IntakeCard = {
  questions: [
    {
      key: "purpose",
      header: "目的",
      question: "今回、何ができるようになりたいですか？",
      options: [{ label: "仕事で使う", description: "" }],
      multi_select: false,
      preselected: [],
    },
    {
      key: "source",
      header: "教材",
      question: "何を使って学びますか？（複数選択可）",
      options: [{ label: "書籍", description: "" }],
      multi_select: true,
      preselected: [],
    },
  ],
};

describe("VoiceIntakePrompt", () => {
  it("shows every question without the clickable options", () => {
    render(<VoiceIntakePrompt card={card} onSkip={vi.fn()} />);

    expect(
      screen.getByText("今回、何ができるようになりたいですか？"),
    ).toBeInTheDocument();
    expect(screen.getByText("何を使って学びますか？")).toBeInTheDocument();
    expect(screen.queryByText("仕事で使う")).not.toBeInTheDocument();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
  });

  it("skips all questions with empty answers", async () => {
    const onSkip = vi.fn();
    render(<VoiceIntakePrompt card={card} onSkip={onSkip} />);

    await userEvent.click(
      screen.getByRole("button", { name: "すべてスキップして始める" }),
    );

    expect(onSkip).toHaveBeenCalledWith(ALL_SKIPPED_TEXT, {
      purpose: "",
      source: [],
      prior_knowledge: "",
    });
  });

  it("does not skip while disabled", async () => {
    const onSkip = vi.fn();
    render(<VoiceIntakePrompt card={card} disabled onSkip={onSkip} />);

    await userEvent.click(
      screen.getByRole("button", { name: "すべてスキップして始める" }),
    );

    expect(onSkip).not.toHaveBeenCalled();
  });
});
