import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { NoteFeedbackPanel } from "@/components/notes/note-feedback-panel";
import type { Feedback } from "@/lib/feedback";

const FIRST: Feedback = {
  id: "f1",
  understanding_level: "low",
  strength: "・用語を自分の言葉で言い換えられた",
  improvements: "・計算量の見積もりが曖昧",
  session_type: "learning",
  created_at: "2026-06-01T00:00:00Z",
};

const LATEST: Feedback = {
  id: "f2",
  understanding_level: "high",
  strength: "・計算量を O(log n) と説明できた",
  improvements: "・再帰と反復の違いを確認する",
  session_type: "review",
  created_at: "2026-06-05T00:00:00Z",
};

describe("NoteFeedbackPanel", () => {
  it("shows the empty state when there is no feedback", () => {
    render(<NoteFeedbackPanel feedbacks={[]} />);
    expect(
      screen.getByText("フィードバックはまだありません"),
    ).toBeInTheDocument();
  });

  it("shows the latest evaluation with its date and source", () => {
    render(<NoteFeedbackPanel feedbacks={[FIRST, LATEST]} />);
    const latest = screen.getByRole("article");
    expect(within(latest).getByText("理解度: 高")).toBeInTheDocument();
    expect(within(latest).getByText("2026年6月5日 の復習")).toBeInTheDocument();
    expect(
      within(latest).getByRole("heading", { name: "強み" }),
    ).toBeInTheDocument();
    expect(
      within(latest).getByText("計算量を O(log n) と説明できた"),
    ).toBeInTheDocument();
  });

  it("lists older evaluations under これまでの評価", () => {
    render(<NoteFeedbackPanel feedbacks={[FIRST, LATEST]} />);
    const history = screen.getByRole("region", { name: "これまでの評価" });
    expect(
      within(history).getByText("2026年6月1日 の学習"),
    ).toBeInTheDocument();
    expect(within(history).getByText("理解度: 低")).toBeInTheDocument();
    expect(
      within(history).getByText("計算量の見積もりが曖昧"),
    ).toBeInTheDocument();
  });

  it("omits the history and the source label when not available", () => {
    render(
      <NoteFeedbackPanel feedbacks={[{ ...LATEST, session_type: null }]} />,
    );
    expect(
      screen.queryByRole("region", { name: "これまでの評価" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("2026年6月5日")).toBeInTheDocument();
  });
});
