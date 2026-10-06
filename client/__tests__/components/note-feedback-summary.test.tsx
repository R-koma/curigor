import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { NoteFeedbackSummary } from "@/components/notes/note-feedback-summary";
import type { Feedback } from "@/lib/feedback";

const OLD: Feedback = {
  id: "f1",
  understanding_level: "low",
  strength: "",
  improvements: "・一つ目\n・二つ目\n・三つ目",
  session_type: "learning",
  created_at: "2026-06-01T00:00:00Z",
};

const LATEST: Feedback = {
  ...OLD,
  id: "f2",
  understanding_level: "medium",
  improvements: "・一つ目\n・二つ目",
  session_type: "review",
  created_at: "2026-06-05T00:00:00Z",
};

describe("NoteFeedbackSummary", () => {
  it("renders nothing without feedback", () => {
    const { container } = render(<NoteFeedbackSummary feedbacks={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("summarizes the latest evaluation and jumps to the feedback", () => {
    render(<NoteFeedbackSummary feedbacks={[OLD, LATEST]} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "#feedback");
    expect(link).toHaveTextContent("理解度: 中");
    expect(link).toHaveTextContent("改善点 2 件");
  });

  it("says there are no improvements when the list is empty", () => {
    render(
      <NoteFeedbackSummary feedbacks={[{ ...LATEST, improvements: "" }]} />,
    );
    expect(screen.getByRole("link")).toHaveTextContent("改善点なし");
  });
});
